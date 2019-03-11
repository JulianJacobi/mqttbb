# MQTT Broadcast Bridge

MQTT Broadcast Bridge is a simple framework to connect
broadast devices like video mixers, audio mixers or video routers
to an MQTT based automation.

This framework is build so simple, that modules can be written
for any protocol you want to integrate to an MQTT automation.

## Install

Basically just install this repo as pip module and execute

    python3 -m mqttbb -p <path to persistence file>


## Configuration

mqttbb searches for a configuration file on following locations:

* `/etc/mqttbb/config.ini`
* file given with `-c` command line option

A sample configuration file can be found in the config folder of this repo.

## Usage

You can install modules for mqttbb via pip and add the module name to
the `modules` config option under the `[General]` section in config file
as comma separated list.

The configuration of the modules is fully done in the
webinterface under the url you configured in config file.