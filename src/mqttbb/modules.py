from mqttbb.exceptions import ConfigError, PathNotRegistered, PathAlreadyRegistered, ConfigCheckError
import json


class Module:

    name = ""

    config = []

    def __init__(self, config, on_path_register=lambda p: True, on_publish=lambda p, m, r: True, *args, **kwargs):
        self.__paths = {}
        self._config = config
        self._config_checked = {}
        self.__config_check(config)
        self.on_path_register = on_path_register
        self.__on_publish = on_publish

    @property
    def paths(self):
        return self.__paths

    @property
    def config_values(self):
        return self._config

    def publish_message(self, path, message, retain=False):
        """
        checks if path to publish is registered by module and forward publish to __on_publish callback

        :param path: path to publish to
        :param message: message to publish
        :param retain: retain flag
        :return:
        """
        if path not in self.__paths:
            raise PathNotRegistered
        self.__on_publish(path, message, retain)

    def __config_check(self, config):
        """
        checks given config and stores it to self.__config_checked

        :param config:
        :return:
        """
        for definition in self.config:
            type = definition.get('type', 'string')
            name = definition.get('name', None)
            default = definition.get('default', None)
            if name not in config:
                if default is not None:
                    config[name] = default
                else:
                    raise ConfigError(message="Option needed", config_name=definition.name)

            try:
                self._config_checked[name] = getattr(self, '_check_{}'.format(type))(config[name])
            except AttributeError:
                pass
            except ConfigCheckError as e:
                raise ConfigError(message=e.message, config_name=name)

    def _check_string(self, value):
        """
        check method for string check

        :param value:
        :return:
        """
        return str(value)

    def _check_integer(self, value):
        """
        check method for integer check

        :param value:
        :return:
        """
        return int(value)

    def _register_path(self, path: str, name: str, description: str, callback, readonly: bool=False):
        """
        method to register mqtt path for module

        :param path: mqtt path
        :param name: name of the path
        :param description: description of the path
        :param callback: function to call on incoming message
        :param readonly: set to false if state change from outside is possible
        :return:
        """
        if path in self.__paths or path == 'meta':
            raise PathAlreadyRegistered()
        self.__paths[path] = {
            'path': path,
            'name': name,
            'description': description,
            'callback': callback,
            'readonly': readonly,
        }
        self.on_path_register(path)
        self.__update_module_meta()

    def __update_module_meta(self):
        """
        send module meta retained to modules meta topic
        :return:
        """
        meta = []

        for path in self.__paths.values():
            meta.append({
                'path': path['path'],
                'name': path['name'],
                'description': path['description'],
                'readonly': path['readonly'],
            })
        self.__on_publish('meta', json.dumps('meta'), True)

    def on_message(self, path, message):
        """
        function called on incoming message for this module and forward the message to path callback

        :param path: mqtt topic of message
        :param message: message payload
        :return:
        """
        if path in self.__paths:
            self.__paths[path]['callback'](path, message)

    def shutdown(self):
        """
        subclasses should implement this method for graceful shutdown of running threads and open connections.
        :return:
        """
        pass


if __name__ == '__main__':
    Module = __import__('mqttbb_module_test').Module

    test_module = Module({'test': 'Testing'})

    pass
