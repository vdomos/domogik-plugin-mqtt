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

MQTT sensors

Implements
==========

- MQTTManager

@author: domos  (domos p vesta at gmail p com)
@copyright: (C) 2007-2016 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

from domogik.common.plugin import Plugin
from domogikmq.message import MQMessage

from domogik_packages.plugin_mqtt.lib.mqtt import MQTT
from domogik_packages.plugin_mqtt.lib.mqtt import MQTTException
import threading
import traceback


class MQTTManager(Plugin):
    """
    """

    # -------------------------------------------------------------------------------------------------
    def __init__(self):
        """ Init plugin
        """
        Plugin.__init__(self, name='mqtt')

        # check if the plugin is configured. If not, this will stop the plugin and log an error
        if not self.check_configured():
            return

        # ### get all config keys
        self.mqtthost = self.get_config("mqtt_host")  
        self.mqttport = self.get_config("mqtt_port")     
        self.mqtttopic = []                             # Ex.: [("domogik/sensor1/#", 0), ("domogik/sensor2/#", 0)]


        # ### get the devices list
        # for this plugin, if no devices are created we won't be able to use devices.
        self.devices = self.get_device_list(quit_if_no_device=True)
        # self.log.info(u"==> device:   %s" % format(self.devices))

        # get the sensors id per device :
        self.sensors = self.get_sensors(self.devices)
        # self.log.info(u"==> sensors:   %s" % format(self.sensors))        # ==> sensors:   {'device id': 'sensor name': 'sensor id'}

        # ### For each device
        self.device_list = {}
        for a_device in self.devices:
            # self.log.info(u"a_device:   %s" % format(a_device))

            device_name = a_device["name"]                                      # Ex.: "Temp atelier"
            device_id = a_device["id"]                                          # Ex.: "72"
            device_type = a_device["device_type_id"]                            # Ex.: "mqtt.sensor_temperature | mqtt.cmd_switch | ..."
            device_topic = self.get_parameter(a_device, "topic")                # Ex.: "domogik/maison/ateliertemp"
            device_qos = self.get_parameter(a_device, "qos")                    # Ex.: 0
            
            self.device_list.update({device_id : {'name': device_name, 'topic': device_topic, 'type' : device_type, 'qos' : device_qos}})
            self.log.info(u"==> Device '{0}', id '{1}', type '{2}', topic '{3}', qos '{4}'".format(device_name, device_id, device_type, device_topic, device_qos))
            
            if "sensor" in device_type:        
                self.log.info(u"==> MQTT topic '%s' from server '%s:%s' will be subscribed for '%s' device Sensor" % (device_topic, self.mqtthost, int(self.mqttport), device_name))
                self.mqtttopic.append(((str(device_topic) + '/#'), int(device_qos)))
            else:
                self.log.info(u"==> MQTT topic '%s' to server '%s:%s' will be published by '%s' device Command" % (device_topic, self.mqtthost, int(self.mqttport), device_name))

        # Init MQTT
        self.mqttClient = MQTT(self.log, self.send_pub_data, self.get_stop(), self.mqtthost, self.mqttport, self.mqtttopic, self.device_list)

        # Connect to MQTT server
        try:
            self.mqttClient.connect()
        except MQTTException as e:
            self.log.error(e.value)
            print(e.value)
            self.force_leave()
            return

        # Start mqtt listen
        threads = {}
        thr_name = "mqtt-sub-listen"
        threads[thr_name] = threading.Thread(None,
                                              self.mqttClient.listensub,
                                              thr_name,
                                              ( self.get_stop(),),
                                              {})
        threads[thr_name].start()
        self.register_thread(threads[thr_name])

        self.ready()



    # -------------------------------------------------------------------------------------------------
    def send_pub_data(self, device_id, value):
        """ Send the sensors values over MQ
        """
        data = {}
        for sensor in self.sensors[device_id]:                  #
            data[self.sensors[device_id][sensor]] = value       # sensor = 'sensor name' in info.json file
        self.log.debug(u"==> Update Sensor '%s' for device id %s (%s)" % (format(data), device_id, self.device_list[device_id]["name"]))    # {u'id': u'value'}

        try:
            self._pub.send_event('client.sensor', data)
        except:
            # We ignore the message if some values are not correct
            self.log.error(u"### Bad MQ message to Pub. This may happen due to some invalid data. MQ data is : {0}".format(data))
            pass


    # -------------------------------------------------------------------------------------------------
    def on_mdp_request(self, msg):
        """ Called when a MQ req/rep message is received
        """
        Plugin.on_mdp_request(self, msg)
        # self.log.info(u"==> Received 0MQ messages: %s" % format(msg))
        if msg.get_action() == "client.cmd":
            reason = None
            status = True
            data = msg.get_data()

            device_id = data["device_id"]
            command_id = data["command_id"]
            if device_id not in self.device_list:
                self.log.error(u"### MQ REQ command, Device ID '%s' unknown, Have you restarted the plugin after device creation ?" % device_id)
                status = False
                reason = u"Plugin mqtt: Unknown device ID %d" % device_id
                self.send_rep_ack(status, reason, command_id, "unknown") ;                      # Reply MQ REP (acq) to REQ command
                return

            device_name = self.device_list[device_id]["name"]
            self.log.info(u"==> Received for device '%s' MQ REQ command message: %s" % (device_name, format(data)))         # {u'value': u'1', u'command_id': 80, u'device_id': 193}
            
            status, reason = self.mqttClient.pubcmd(self.device_list[device_id]["topic"], self.device_list[device_id]["qos"], data["value"], device_id)
            if status:
                self.send_pub_data(device_id, data["value"])    # Update sensor command.
            
            # Reply MQ REP (acq) to REQ command
            self.send_rep_ack(status, reason, command_id, device_name) ;


    # -------------------------------------------------------------------------------------------------
    def send_rep_ack(self, status, reason, cmd_id, dev_name):
        """ Send MQ REP (acq) to command
        """
        self.log.info(u"==> Reply MQ REP (acq) to REQ command id '%s' for device '%s'" % (cmd_id, dev_name))
        reply_msg = MQMessage()
        reply_msg.set_action('client.cmd.result')
        reply_msg.add_data('status', status)
        reply_msg.add_data('reason', reason)
        self.reply(reply_msg.get())

if __name__ == "__main__":
    MQTTManager()
