from paho.mqtt.client import Client, MQTTMessage
from mqttbb.modules import Module as BaseModule
from mqttbb.exceptions import InstanceAlreadyExists, PersistenceException
import logging
import uuid
import time
import json
import re
import threading
import bottle


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

    def __read_persistence_file(self):
        if self.__persistence_file is None:
            return
        persistence = json.load(open(self.__persistence_file, 'r'))
        for instance in persistence:
            if instance['module'] not in self.available_modules:
                success = self.add_module(instance['module'])
                if not success:
                    raise PersistenceException('Module "{}" is needed for load persistence but '
                                               'seems not to be installed.'
                                               .format(instance['module']))
            self.add_module_instance(instance['module'], instance['config'], instance['uuid'])

    def __update_persistence_file(self):
        if self.__persistence_file is None:
            return

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
                t = threading.Thread(target=self.instances[match.group(1)].on_message,
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

    def add_module_instance(self, name, config, instance_id=None):
        """
        Add module instance to broadcast bridge

        :param name: name of the module
        :param config: config object for the module
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

        self.instances[instance_id] = self.available_modules[name](config,
                                                                   on_path_register=on_path_register,
                                                                   on_publish=on_publish)

        self.__update_mqtt_service_meta()

    def __update_mqtt_service_meta(self):
        instances = []
        for i, instance in self.instances.items():
            instances.append({'id': i, 'name': instance.name})
        self.mqtt_client.publish('{}meta'.format(self.__mqtt_prefix), json.dumps(instances), retain=True)

    def __init_http_server(self):
        """
        initialize http server (creating routes and config)
        :return: void
        """


if __name__ == '__main__':
    logger = logging.getLogger('mqttbb')
    logger.setLevel(logging.DEBUG)
    bb = BroadcastBridge()

    bb.add_module('mqttbb_module_test')

    bb.add_module_instance('mqttbb_module_test', {'test': 'test'})

    time.sleep(100)
