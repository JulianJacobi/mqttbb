from paho.mqtt.client import Client, MQTTMessage
from mqttbb.modules import Module as BaseModule
from mqttbb.exceptions import InstanceAlreadyExists, PersistenceException, ConfigError
import logging
import uuid
import time
import json
import re
import threading
import bottle
import os
import functools


class BroadcastBridge:
    """
    Main Class of the Broadcast Bridge
    """

    def __init__(self, broker_host: str="localhost", broker_port: int=1883, http_host="localhost", http_port=8080,
                 mqtt_prefix='broadcast_bridge/', persistence_file=None):
        self.mqtt_client = Client()
        self.mqtt_client.connect(broker_host, broker_port)
        self.mqtt_client.loop_start()
        self.mqtt_client.on_message = self.__on_mqtt_message
        self.__mqtt_prefix = mqtt_prefix

        self.http_port = http_port
        self.http_host = http_host

        self.available_modules = {}

        self.instances = {}
        self.log = logging.getLogger('mqttbb')
        self.log.setLevel(logging.DEBUG)

        self.__persistence_file = persistence_file

        self.__read_persistence_file()

        self.__init_http_server()

    def __read_persistence_file(self):
        if self.__persistence_file is None:
            return
        try:
            persistence = json.load(open(self.__persistence_file, 'r'))
            for instance in persistence:
                if instance['module'] not in self.available_modules:
                    success = self.add_module(instance['module'])
                    if not success:
                        raise PersistenceException('Module "{}" is needed for load persistence but '
                                                   'seems not to be installed.'
                                                   .format(instance['module']))
                self.add_module_instance(instance['module'],
                                         instance['config'],
                                         instance['short_description'],
                                         instance['uuid'])
        except FileNotFoundError:
            return

    def __update_persistence_file(self):
        if self.__persistence_file is None:
            return

        instances = []
        for i, instance in self.instances.items():
            instances.append({
                'module': instance['module'],
                'config': instance['instance'].config_values,
                'uuid': i,
                'short_description': instance['short_description'],
            })
        json.dump(instances, open(self.__persistence_file, 'w+'))

    def __on_mqtt_message(self, client, user_data, message: MQTTMessage):
        """
        receives MQTT message and forward it to the right module

        :param client:
        :param user_data:
        :param message:
        :return:
        """
        if message.topic.startswith(self.__mqtt_prefix):
            last = message.topic[len(self.__mqtt_prefix):]
            match = re.match(r'^(.*)/(.*)$', last)
            if match.group(1) in self.instances:
                t = threading.Thread(target=self.instances[match.group(1)]['instance'].on_message,
                                     args=(match.group(2), message.payload))
                t.start()

    def add_module(self, name):
        """
        Add module to bridge and check if the given module exists and is compatible.

        :param name: name of the module
        :return: Success state
        """
        try:
            module = __import__(name)
            module_class = module.Module
            if module_class == BaseModule:
                self.log.error('The module class seems to be a copy of base Module in "{}"'.format(name))
            if not issubclass(module.Module, BaseModule):
                self.log.error('Given module "{}" is not valid: Class Module is not inherit from mqttbb.modules.Module'
                               .format(name))
            for config in module_class.config:
                if 'name' not in config:
                    self.log.error('Config definition error, missing name in module "{}"'.format(name))
                    return False
                if 'title' not in config:
                    config['title'] = config['name']
                if 'type' not in config:
                    self.log.error('Config definition error, missing type in module "{}"'.format(name))
                    return False
            if name in self.available_modules:
                self.log.warning('Module already loaded.')
                return False
            self.available_modules[name] = module_class
            return True
        except ModuleNotFoundError:
            self.log.error('Module not found "{}"'.format(name))
        except AttributeError:
            self.log.error('Given module "{}" is not valid: No class "Module" found'.format(name))

        return False

    def add_module_instance(self, name, config, short_description="", instance_id=None):
        """
        Add module instance to broadcast bridge

        :param name: name of the module
        :param config: config object for the module
        :param short_description: short description
        :param instance_id: id of the instance if already exists
        :return: void
        """
        if not isinstance(config, dict):
            raise TypeError("config must be dict")
        if name not in self.available_modules:
            raise ModuleNotFoundError()
        if instance_id is None:
            instance_id = str(uuid.uuid4())

        if instance_id in self.instances:
            raise InstanceAlreadyExists('Instance id is already registered.')

        def on_path_register(path):
            full_path = "{}{}/{}".format(self.__mqtt_prefix, instance_id, path)
            self.mqtt_client.subscribe(full_path)
            self.log.debug('Module "{}" registered topic "{}"'.format(name, full_path))

        def on_publish(path, payload, retain=False):
            full_path = "{}{}/{}".format(self.__mqtt_prefix, instance_id, path)
            self.mqtt_client.publish(full_path, payload, retain=retain)

        self.instances[instance_id] = {
            'instance': self.available_modules[name](config,
                                                     on_path_register=on_path_register,
                                                     on_publish=on_publish),
            'short_description': short_description,
            'module': name
        }

        self.__update_mqtt_service_meta()

    def remove_module_instance(self, uid):
        if uid not in self.instances:
            return
        instance = self.instances[uid]['instance']
        for path in instance.paths:
            full_path = "{}{}/{}".format(self.__mqtt_prefix, uid, path)
            self.mqtt_client.unsubscribe(full_path)
        instance.shutdown()
        del self.instances[uid]

        self.__update_mqtt_service_meta()

    def __update_mqtt_service_meta(self):
        instances = []
        for i, instance in self.instances.items():
            instances.append({
                'id': i,
                'name': instance['instance'].name,
                'short_description':instance['short_description']
            })
        self.mqtt_client.publish('{}meta'.format(self.__mqtt_prefix), json.dumps(instances), retain=True)
        self.__update_persistence_file()

    def __init_http_server(self):
        """
        initialize http server (creating routes and config)
        :return: void
        """

        bootstrap_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                      'static/bootstrap/dist/css/bootstrap.min.css')
        
        template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static/templates/')

        view = functools.partial(bottle.jinja2_view, template_lookup=[template_dir])

        @bottle.get('/css/bootstrap')
        def bootstrap():
            return bottle.static_file(os.path.basename(bootstrap_path), os.path.dirname(bootstrap_path))

        @bottle.get('/css/bootstrap.min.css.map')
        def bootstrap_map():
            return bottle.static_file(os.path.basename(bootstrap_path)+'.map', os.path.dirname(bootstrap_path))

        @bottle.get('/')
        @view('overview.j2', )
        def index():
            available_modules = []
            for i, module in self.available_modules.items():
                available_modules.append({
                    'name': module.name,
                    'id': i,
                })
            instances = []
            for i, instance in self.instances.items():
                instances.append({
                    'short_description': instance['short_description'],
                    'uid': i,
                    'module': instance['module'],
                    'module_name': instance['instance'].name,
                })

            return {'available_modules': available_modules, 'instances': instances}

        @bottle.get('/info/<uid>')
        @view('info.j2')
        def info(uid):
            if uid not in self.instances:
                bottle.redirect('/')
            instance = self.instances[uid]

            return {
                'short_description': instance['short_description'],
                'uid': uid,
                'module': instance['module'],
                'module_name': instance['instance'].name,
                'config': instance['instance'].config,
                'config_values': instance['instance'].config_values,
                'paths': instance['instance'].paths.values(),
                'path_prefix': '{}{}/'.format(self.__mqtt_prefix, uid),
            }

        @bottle.route('/delete/<uid>', ['GET', 'POST'])
        @view('delete.j2')
        def delete(uid):
            if uid not in self.instances:
                bottle.redirect('/')
                return
            if bottle.request.method == 'POST':
                self.remove_module_instance(uid)
                bottle.redirect('/')
                return
            instance = self.instances[uid]

            return {
                'short_description': instance['short_description'],
                'uid': uid,
                'module': instance['module'],
                'module_name': instance['instance'].name,
            }

        @bottle.get('/add', ['GET', 'POST'])
        @view('form.j2')
        def add():
            errors = {}
            module = bottle.request.GET.get('module_id')
            if module is None or module not in self.available_modules:
                return bottle.redirect('/')

            config = self.available_modules[module].config
            config_values = {}
            short_description = ""

            if bottle.request.method == 'POST':
                form_dict = dict(bottle.request.forms)
                short_description = form_dict['short_description']
                if short_description == '':
                    errors['short_description'] = 'Angabe erforderlich'
                for element in config:
                    if element['name'] in form_dict:
                        config_values[element['name']] = form_dict[element['name']]
                try:
                    if len(errors) == 0:
                        self.add_module_instance(module, form_dict, short_description=short_description)
                        bottle.redirect('/')
                except ConfigError as e:
                    errors[e.config_name] = e.message

            return {'errors': errors, 'config': config, 'module': module, 'values': config_values,
                    'short_description': short_description}


    def http_loop(self):
        """
        start http server as blocking loop

        :return:
        """

        bottle.run(host=self.http_host, port=self.http_port)



if __name__ == '__main__':
    logger = logging.getLogger('mqttbb')
    logger.setLevel(logging.DEBUG)
    bb = BroadcastBridge()

    bb.add_module('mqttbb_module_test')

    bb.add_module_instance('mqttbb_module_test', {'test': 'test'})

    time.sleep(100)
