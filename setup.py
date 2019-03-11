#! /usr/bin/env python3

from distutils.core import setup

setup(
    name="mqttbb",
    version='1.0',
    description='MQTT Broadcast Bridge',
    long_description='Bridge to integrate broadcast devices '
                     'like video mixers, audio mixers or routers in mqtt automation.',
    author='Julian Jacobi',
    author_email='mail@julianjacobi.net',
    packages=['mqttbb'],
    package_dir={'mqttbb': 'src/mqttbb/'},
    install_requires=[
        'paho-mqtt',
        'bottle',
        'jinja2'
    ],
    package_data=[
        'src/mqttbb/static/bootstrap/dist/css/bootstrap.min.css'
        'src/mqttbb/static/bootstrap/dist/css/bootstrap.min.css.map'
        'src/mqttbb/static/template/*'
    ],
)
