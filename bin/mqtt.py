#!/usr/bin/python
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

MQTT

Implements
==========

- MQTTManager

@author: domos  (domos p vesta at gmail p com)
@copyright: (C) 2007-2015 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

from domogik.xpl.common.xplmessage import XplMessage
from domogik.xpl.common.xplconnector import Listener
from domogik.xpl.common.plugin import XplPlugin

from domogik_packages.plugin_mqtt.lib.mqtt import MQTT
from domogik_packages.plugin_mqtt.lib.mqtt import MQTTException
import threading
import traceback


class MQTTManager(XplPlugin):
	""" 
	"""

	def __init__(self):
		""" Init plugin
		"""
		XplPlugin.__init__(self, name='mqtt')

 		# Configuration
		self.mqtthost = self.get_config("mqtt_host")						 # MQTT server
		if self.mqtthost == None:
			self.log.error('### MQTT server is not configured, exiting') 
			self.force_leave()
			return
		self.mqttport = self.get_config("mqtt_port")						 # MQTT server port
		if self.mqttport == None:
			self.log.error('### MQTT server port is not configured, exiting') 
			self.force_leave()
			return
		self.mqtttopic = self.get_config("mqtt_topic")						 # MQTT domogik topic
		if self.mqtttopic == None:
			self.mqtttopic = "domogik"

		self.mqtt_manager = MQTT(self.log, self.send_xpl, self.get_stop(), self.mqtthost, self.mqttport, self.mqtttopic)

       # Connecte to MQTT server
		try:
			self.mqtt_manager.connect()
		except MQTTException as e:
			self.log.error(e.value)
			print(e.value)
			self.force_leave()
			return

		# Start mqtt listen
		mqtt_process = threading.Thread(None,
								   self.mqtt_manager.listen,
								   "mqtt-process-listen",
								   (self.get_stop(),),
								   {})
		self.register_thread(mqtt_process)
		mqtt_process.start()

		self.ready()


	def send_xpl(self, message = None, schema = None, data = {}):
		""" Send xPL message on network
		"""
		self.log.debug(u"send_xpl : Send xPL message xpl-trig : schema:{0}, data:{1}".format(schema, data))
		msg = XplMessage()
		msg.set_type("xpl-trig")
		msg.set_schema(schema)
		for key in data:
			msg.add_data({key : data[key]})
		self.myxpl.send(msg)



if __name__ == "__main__":
	MQTTManager()
