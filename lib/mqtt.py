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
import paho.mqtt.client as mqtt

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

	def __init__(self, log, cb_send_xpl, stop, mqtthost, mqttport, mqtttopic):
		""" 
		"""
		self.log = log
		self.cb_send_xpl = cb_send_xpl
		self.stop = stop

		self.mqtthost = mqtthost
		self.mqttport = mqttport
		self.mqtttopic = str(mqtttopic + '/#')		# 'str' car il n'est pas reconnu comme une chaine (isinstance) par la fonction subscrib !!!
		self.log.info("### MQTT topic '%s' from server '%s:%s' will be listen" % (self.mqtttopic, self.mqtthost, int(self.mqttport)))

		self.MQTTClient = mqtt.Client('mqtt2dmg')
		self.MQTTClient.on_connect = self.on_connect
		self.MQTTClient.on_message = self.on_message
		self.MQTTClient.on_disconnect = self.on_disconnect


	# -------------------------------------------------------------------------------------------------
	def on_connect(self, client, userdata, flags, rc):			# The callback for when the client receives a CONNACK response from the server.
		if rc == 0:
			self.log.info("### Connection to MQTT broquer successful, (Result code 0)")
			self.MQTTClient.subscribe(self.mqtttopic)				# Subscribing in on_connect() means that if we lose the connection and econnect then subscriptions will be renewed.
		else:
			self.log.error("### Connection to MQTT broquer unsuccessful, (Result code " + str(rc) + ": " + CONNECT_RESULT_CODES[rc] + ")") 
			self.MQTTClient.disconnect				# Stop the loop from trying to connect again if unsuccessful.
		
	# -------------------------------------------------------------------------------------------------
	def on_disconnect(self, client, userdata, rc):
		self.log.info("Connection to MQTT broquer has been lost.") 
		self.log.info("Attempting to reconnect in 20s.")		# This will automatically reconnect if connection is lost.
		time.sleep(20)   
		self.MQTTClient.connect(MQTTHOST, 1883, 60)


	# -------------------------------------------------------------------------------------------------
	def on_message(self, client, userdata, msg):		# The callback for when a PUBLISH message is received from the broquer.
		self.log.info("Received MQTT message:  %s = %s" % (msg.topic, msg.payload))
		try:
			(topic, xpldevice, xpltype) = msg.topic.split('/')
		except ValueError:
			self.log.error("### Incorrectly formatted Topic message '%s', ignore it." % msg.topic)
			return

		xplcurrent = msg.payload
		self.cb_send_xpl(schema = "sensor.basic",
						 data  = {"device" : xpldevice,
								  "type" : xpltype,
								  "current" : xplcurrent})

	# -------------------------------------------------------------------------------------------------
	def connect(self):
		self.log.info("### Connecting to MQTT broquer ...")
		try:
			self.MQTTClient.connect(self.mqtthost, int(self.mqttport), 60)
			self.log.info("### Connected on MQTT broquer")
		except:
			error = "Error while connecting to MQTT broquer : %s " % str(traceback.format_exc())
			raise MQTTException(error)


	# -------------------------------------------------------------------------------------------------
	def listen(self, stop):
		""" Start listening to mqtt topic messages
		@param stop : an Event to wait for stop request
		"""
		while not stop.isSet():
			self.MQTTClient.loop()
		self.log.info("Stop listening MQTT message.") 
		
# -------------------------------------------------------------------------------------------------


