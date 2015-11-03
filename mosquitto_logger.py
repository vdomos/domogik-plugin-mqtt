#!/usr/bin/env python
# -*- coding: utf-8 -*-                                                                    

'''
Doc module mqtt pyhton:
https://pypi.python.org/pypi/paho-mqtt

11/6/2015
Utilisation de logging

18/4/2015
Prenière verison de logger mqtt.

'''

import paho.mqtt.client as mqtt
#import datetime
import logging
import signal
import time

MQTTHOST="jdom"

# -------------------------------------------------------------------------------------------------
# Result codes and their explanations for connection failure debugging.
CONNECT_RESULT_CODES = {
    0: 'Connection successful',
    1: 'Incorrect protocol version',
    2: 'Invalid client identifier',
    3: 'Server unavailable',
    4: 'Bad username or password',
    5: 'Not authorized'
}

LOG_FILENAME = '/var/log/mqtt/mqtt_logger.log'
run = True

# -------------------------------------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):			# The callback for when the client receives a CONNACK response from the server.
	if rc == 0:
		print("Connection successful, (Result code 0)")
		mqttc.subscribe("#")				# Subscribing in on_connect() means that if we lose the connection and econnect then subscriptions will be renewed.
	else:
		print("Connection unsuccessful, (Result code " + str(rc) + ": " + CONNECT_RESULT_CODES[rc] + ")") 
 		mqttc.disconnect				# Stop the loop from trying to connect again if unsuccessful.
        
# -------------------------------------------------------------------------------------------------
def on_disconnect(client, userdata, rc):
	print("Connection has been lost.") 
	print("Attempting to reconnect in 20s.")		# This will automatically reconnect if connection is lost.
	time.sleep(20)   
	mqttc.connect(MQTTHOST, 1883, 60)


# -------------------------------------------------------------------------------------------------
def on_message(client, userdata, msg):			# The callback for when a PUBLISH message is received from the server.
    #print("%s  %s  %s   %s" % (datetime.datetime.now(), msg.retain, msg.topic, msg.payload))
    logger.info("%d  %s  %s" % (msg.qos, msg.topic, msg.payload))


# -------------------------------------------------------------------------------------------------
def on_log(client, obj, level, string):
    print("MQTT log: %s %s" % (str(level), string))

# -------------------------------------------------------------------------------------------------
def signal_handler(signal, frame):
	print(' Exit program !')
	global run
	run = False

# -------------------------------------------------------------------------------------------------
logger = logging.getLogger('mosquitto_logger')
logger.setLevel(logging.DEBUG)

# Create a file handler and set level to debug
loghandler = logging.FileHandler(LOG_FILENAME, mode='a', encoding=None, delay=False)
loghandler.setLevel(logging.DEBUG)

# Create formatter
#logformatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logformatter = logging.Formatter('%(asctime)s  %(message)s')

# Add formatter to loghandler
loghandler.setFormatter(logformatter)

# Add loghandler to logger
logger.addHandler(loghandler)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


mqttc = mqtt.Client("mosquitto_logger")
mqttc.on_connect = on_connect
mqttc.on_message = on_message
#mqttc.on_log = on_log
mqttc.on_disconnect = on_disconnect

mqttc.connect(MQTTHOST, 1883, 60)
print('MQTT messages log in file: %s' % LOG_FILENAME)

#mqttc.loop_forever()	# Blocking call that processes network traffic, dispatches callbacks and handles reconnecting.

while run:
    mqttc.loop()
   
