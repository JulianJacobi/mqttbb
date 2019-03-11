from argparse import ArgumentParser, FileType
from configparser import ConfigParser
from mqttbb.core import BroadcastBridge
import os


def main():

    parser = ArgumentParser()

    parser.add_argument('-c --config', metavar='CONFIGFILE', required=False,
                        help='Path to config file.', default='', type=FileType, dest='config')
    parser.add_argument('-p --persistence_file', metavar='FILE', required=True,
                        help='File to store persistence information to.', type=FileType, dest='persistence_file')

    args = parser.parse_args()

    config = ConfigParser()
    config_files = [
        '/etc/mqttbb/config.ini',
    ]
    if os.path.isfile(args.config._mode):
        config_files.append(args.config._mode)
    else:
        if args.config._mode != '':
            print('Given config file not found.')
            exit(1)
    config.read(config_files)

    bb = BroadcastBridge(
        broker_host=config.get('MQTT', 'host', fallback='localhost'),
        broker_port=config.getint('MQTT', 'port', fallback=1883),
        http_host=config.get('HTTP', 'host', fallback='localhost'),
        http_port=config.getint('HTTP', 'port', fallback=8080),
        mqtt_prefix=config.get('MQTT', 'prefix', fallback='broadcast_bridge/'),
        persistence_file=args.persistence_file._mode,
    )

    for module in str(config.get('General', 'modules', fallback='')).split(','):
        module = module.strip()
        if module != '':
            bb.add_module(module)


if __name__ == '__main__':
    main()


