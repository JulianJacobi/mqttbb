

class ConfigError(Exception):

    def __init__(self, message, config_name):
        self.message = message
        self.config_name = config_name


class PathNotRegistered(Exception):
    pass


class PathAlreadyRegistered(Exception):
    pass


class InstanceAlreadyExists(Exception):
    pass


class PersistenceException(Exception):
    pass
