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
import socket
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

    def __init__(self, log, cb_send, stop, mqtthost, mqttport, mqttprotocol):
        """ INIT
        """
        self.log = log
        self.send = cb_send
        self.stopplugin = stop

        self.mqtthost = mqtthost
        self.mqttport = mqttport
        self.mqttsubtopics = []        
        
        self.numberSensors = ["mqtt.sensor_temperature", "mqtt.sensor_humidity", "mqtt.sensor_brightness",
                              "mqtt.sensor_pressure", "mqtt.sensor_power", "mqtt.sensor_number"]
        self.boolSensors = ["mqtt.sensor_onoff", "mqtt.sensor_openclose", "mqtt.sensor_enabledisable", 
                            "mqtt.sensor_updown", "mqtt.sensor_lowhigh", "mqtt.sensor_state", "mqtt.sensor_motion"]
        
        self.boolStrValue = {"false": "0", "true": "1", "off": "0", "on": "1", "disable": "0", 
                        "enable": "1", "low": "0", "high": "1", "decrease": "0", "increase": "1", 
                        "up": "0", "down": "1", "open": "0", "close": "1", "closed": "1", "stop": "0",
                        "start": "1", "inactive": "0", "active": "1", "nomotion": "0", "motion": "1",
                        "0": "0", "1": "1"}
        
        protocollist = {"MQTTv31" : 3, "MQTTv311" : 4}
        self.MQTTClient = mqtt.Client('mqtt2dmg_' + platform.node(), protocol=protocollist[mqttprotocol])
        # self.MQTTClient = mqtt.Client('mqtt2dmg_' + platform.node(), protocol=3)  # For mosquitto that don't support MQTT version 3.1.1 protocol
        # protocol:  the version of the MQTT protocol to use for this client. Can be either MQTTv31 (3) or MQTTv311 (4)
        ### self.MQTTClient.username_pw_set(mqtt_user, mqtt_pwd)   # For future use, Must be called before connect*()
        self.MQTTClient.on_connect = self.on_connect
        self.MQTTClient.on_message = self.on_message
        self.MQTTClient.on_disconnect = self.on_disconnect
        
        ### loop_start()/loop_stop() methods ?


    # -------------------------------------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        """ The callback when the client receives a CONNACK response from the server.
        """
        if rc == 0:
            self.log.info(u"==> Connection to MQTT broquer successful, (Result code 0)")
            try:  
                if self.mqttsubtopics:
                    self.log.debug(u"==> Subscribe to Topic list:  %s" % format(self.mqttsubtopics))
                    self.MQTTClient.subscribe(self.mqttsubtopics)   # Subscribing in on_connect() means that if we lose the connection and econnect then subscriptions will be renewed.
                else:
                    self.log.info(u"==> No MQTT sensor topic to subscribe")
            except ValueError:      # Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has zero string length, or if topic is not a string, tuple or list.
                raise MQTTException(u"### Subscribing, invalid Qos or Topic in list:  %s" % format(self.mqttsubtopics))
        else:
            raise MQTTException(u"### Connection to MQTT broquer failed, (Result code " + str(rc) + ": " + CONNECT_RESULT_CODES[rc] + ")") 


    # -------------------------------------------------------------------------------------------------
    def on_disconnect(self, client, userdata, rc):
        """ The callback when disconnecting from MQTT server
        """
        if not self.stopplugin.isSet():
            self.log.error(u"### Connection to MQTT broquer has been lost.")
            self.log.error(u"### Waiting for the connection to be back")               # loop_start() will automatically reconnect if connection be back.
        else:
            self.log.info(u"==> MQTT client disconnected by plugin stop")


    # -------------------------------------------------------------------------------------------------
    def on_message(self, client, userdata, msg):
        """ The callback for when a PUBLISH message is received from the broquer.
        """
        self.log.info(u"==> Received subscribed MQTT message:  %s = %s" % (msg.topic, msg.payload))
        for deviceid in self.devicelist:        #  {'70' : {'name': 'Temp Atelier', 'topic': 'domogik/maison/ateliertemp', 'type' : 'mqtt.sensor_temperature', 'qos' : 0}}
            if msg.topic ==  self.devicelist[deviceid]["topic"]:
                if self.devicelist[deviceid]["type"] in self.numberSensors:
                    if not self.is_number(msg.payload):
                        self.log.error(u"### MQTT message '%s' for device '%s' not return a number: '%s'" % (msg.topic, self.devicelist[deviceid]["name"], msg.payload))
                        return
                elif self.devicelist[deviceid]["type"] in self.boolSensors:
                    if msg.payload.lower() not in self.boolStrValue:
                        self.log.error(u"### MQTT message '%s' for device '%s' not return a binary: '%s'" % (msg.topic, self.devicelist[deviceid]["name"], msg.payload))
                        return
                    msg.payload = self.boolStrValue[msg.payload.lower()]
                    
                self.send(deviceid, msg.payload.decode('utf-8', 'ignore'))      # Erreur "UnicodeDecodeError: 'ascii' codec can't decode byte" avec prevision pluie !


    # -------------------------------------------------------------------------------------------------
    def connect(self):
        """ Connect to MQTT server
        """
        self.log.info(u"==> Connecting to MQTT broquer ...")
        try:
            self.MQTTClient.connect(self.mqtthost, int(self.mqttport), 60)
            self.log.info(u"==> Connected on MQTT broquer")
            self.MQTTClient.loop_start()                        # This will automatically reconnect if connection is lost.
        except:
            error = u"### Error while connecting to MQTT broquer : %s " % str(traceback.format_exc())
            raise MQTTException(error)

    # -------------------------------------------------------------------------------------------------
    def mqttloop(self):
        """ Start listening to mqtt topic messages
        """     
        self.log.info(u"==> Start MQTT loop")
        while not self.stopplugin.isSet():
            self.stopplugin.wait(3)
        self.MQTTClient.disconnect()
        self.MQTTClient.loop_stop()

    
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
    def reloadMQTTDevices(self, devices, newsubtopics):
        '''
        '''
        self.devicelist = devices
        self.log.debug(u"==> Topics list:  old='%s', new='%s'" % (format(self.mqttsubtopics), format(newsubtopics)))
        if not self.mqttsubtopics:                   # At start up the subscribe will be done in on_connect callback 
            self.mqttsubtopics = newsubtopics
            return
        for topic in self.mqttsubtopics:
            self.MQTTClient.unsubscribe(topic[0])
        self.mqttsubtopics = newsubtopics
        self.log.debug(u"==> Subscribe to new Topic list:  %s" % format(self.mqttsubtopics))
        self.MQTTClient.subscribe(self.mqttsubtopics)
    
    
    # -------------------------------------------------------------------------------------------------
    def is_number(self, s):
        ''' Return 'True' if s is a number
        '''
        try:
            float(s)
            return True
        except ValueError:
            return False
    
    
    
    
