# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

Handle MQTT server

Implements
==========

- MQTT
- MQTTException

@author: domos  (domos p vesta at gmail p com)
@copyright: (C) 2007-2015 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import traceback
import threading
import time
import datetime
import platform
import paho.mqtt.client as mqtt     # https://pypi.python.org/pypi/paho-mqtt

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


# -------------------------------------------------------------------------------------------------
class MQTTException(Exception):
    """
    MQTT exception
    """

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


# -------------------------------------------------------------------------------------------------
class MQTT:
    """ MQTT
    """

    def __init__(self, log, cb_send, stop, mqtthost, mqttport, mqtttopic, devicelist):
        """ INIT
        """
        self.log = log
        self.send = cb_send
        self.stop = stop
        self.devicelist = devicelist

        self.mqtthost = mqtthost
        self.mqttport = mqttport
        self.mqtttopic = mqtttopic        
        
        self.MQTTClient = mqtt.Client('mqtt2dmg_' + platform.node())
        self.MQTTClient.on_connect = self.on_connect
        self.MQTTClient.on_message = self.on_message
        self.MQTTClient.on_disconnect = self.on_disconnect


    # -------------------------------------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        """ The callback when the client receives a CONNACK response from the server.
        """
        if rc == 0:
            self.log.info(u"==> Connection to MQTT broquer successful, (Result code 0)")
            try:            
                self.MQTTClient.subscribe(self.mqtttopic)   # Subscribing in on_connect() means that if we lose the connection and econnect then subscriptions will be renewed.
            except ValueError:      # Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has zero string length, or if topic is not a string, tuple or list.
                errorstr = u"### There are invalid Qos or Topic in list:  %s" % format(self.mqtttopic)
                self.log.error(errorstr)
                self.MQTTClient.disconnect
        else:
            self.log.error(u"### Connection to MQTT broquer failed, (Result code " + str(rc) + ": " + CONNECT_RESULT_CODES[rc] + ")")
            self.MQTTClient.disconnect                  # Stop the loop from trying to connect again if unsuccessful.


    # -------------------------------------------------------------------------------------------------
    def on_disconnect(self, client, userdata, rc):
        """ The callback when disconnecting from MQTT server
        """
        if not self.stop.isSet():
            self.log.error(u"### Connection to MQTT broquer has been lost.")
            self.log.error(u"### Attempting to reconnect in 20s.")        # This will automatically reconnect if connection is lost.
            time.sleep(20)
            self.MQTTClient.connect(MQTTHOST, 1883, 60)


    # -------------------------------------------------------------------------------------------------
    def on_message(self, client, userdata, msg):
        """ The callback for when a PUBLISH message is received from the broquer.
        """
        self.log.info(u"==> Received subscribed MQTT message:  %s = %s" % (msg.topic, msg.payload))
        for deviceid in self.devicelist:        #  {'70' : {'name': 'Temp Atelier', 'topic': 'domogik/maison/ateliertemp', 'type' : 'mqtt.sensor_temperature', 'qos' : 0}}
            if msg.topic ==  self.devicelist[deviceid]["topic"]:
                if self.devicelist[deviceid]["type"] in ["mqtt.sensor_temperature", "mqtt.sensor_humidity", "mqtt.sensor_number"]:
                    if not self.is_number(msg.payload):
                        self.log.error(u"### MQTT message '%s' for device '%s' not return a number: '%s'" % (msg.topic, self.devicelist[deviceid]["name"], msg.payload))
                        return
                elif self.devicelist[deviceid]["type"] in ["mqtt.sensor_onoff", "mqtt.sensor_openclose"]:
                    if msg.payload not in ['0', '1']:
                        self.log.error(u"### MQTT message '%s' for device '%s' not return a binary: '%s'" % (msg.topic, self.devicelist[deviceid]["name"], msg.payload))
                        return
                self.send(deviceid, msg.payload)

    # -------------------------------------------------------------------------------------------------
    def connect(self):
        """ Connect to MQTT server
        """
        self.log.info(u"==> Connecting to MQTT broquer ...")
        try:
            self.MQTTClient.connect(self.mqtthost, int(self.mqttport), 60)
            self.log.info(u"==> Connected on MQTT broquer")
        except:
            error = u"### Error while connecting to MQTT broquer : %s " % str(traceback.format_exc())
            raise MQTTException(error)


    # -------------------------------------------------------------------------------------------------
    def listensub(self):
        """ Start listening to mqtt topic messages
        """
        self.log.debug(u"==> Listen Topic list:  %s" % format(self.mqtttopic))        # ==> 
     
        while not self.stop.isSet():
            self.MQTTClient.loop()
        self.log.info(u"==> Stop listening MQTT message.")
        self.MQTTClient.disconnect()


    # -------------------------------------------------------------------------------------------------
    def pubcmd(self, topic, qos, value, deviceid):
        """ Publish the command value of the topic
        """
        try:
            self.log.info(u"==> Publish MQTT message:  '%s'='%s' for device name '%s'" % (topic, value, self.devicelist[deviceid]["name"]))
            (result, mid) = self.MQTTClient.publish(str(topic), str(value), int(qos))
        except ValueError:      #  Will be raised if topic is None, has zero length or is invalid (contains a wildcard), if qos is not one of 0, 1 or 2, or if the length of the payload is greater than 268435455 bytes.
            errorstr = u"### Invalid '%s' topic for device name '%s'" % (topic, self.devicelist[deviceid]["name"])
            self.log.error(errorstr)
            return False, errorstr
        
        if result == mqtt.MQTT_ERR_SUCCESS:
            return True, None
        else:
            errorstr = u"### Publishing value '%s' with '%s' topic for device name '%s' has failed." % (value, topic, self.devicelist[deviceid]["name"])
            self.log.error(errorstr)
            return False, errorstr
    
    # -------------------------------------------------------------------------------------------------
    def is_number(self, s):
        ''' Return 'True' if s is a number
        '''
        try:
            float(s)
            return True
        except ValueError:
            return False
    
    
    
    