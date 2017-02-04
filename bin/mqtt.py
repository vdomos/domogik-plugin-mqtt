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

        # Check if the plugin is configured. If not, this will stop the plugin and log an error
        if not self.check_configured():
            return

        # Get all config keys
        self.mqtthost = self.get_config("mqtt_host")  
        self.mqttport = self.get_config("mqtt_port")     
        self.mqttprotocol = self.get_config("mqtt_protocol")        # Old protocol = MQTTv31 (3),  default = MQTTv311 (4)

        # Get the devices list, for this plugin, if no devices are created we won't be able to use devices.
        self.devices = self.get_device_list(quit_if_no_device=True)
        # self.log.info(u"==> device:   %s" % format(self.devices))

        # Get the sensors id per device :
        self.sensors = self.get_sensors(self.devices)
        # self.log.info(u"==> sensors:   %s" % format(self.sensors))        # ==> sensors:   {'device id': 'sensor name': 'sensor id'}

        # Init MQTT
        self.mqttClient = MQTT(self.log, self.send_pub_data, self.get_stop(), self.mqtthost, self.mqttport, self.mqttprotocol)

        # Set MQTT devices list
        self.setMqttDevicesList(self.devices)

        # Connect to MQTT server
        try:
            self.mqttClient.connect()
        except MQTTException as e:
            self.log.error(e.value)
            print(e.value)
            self.force_leave()
            return

        # Start mqtt loop
        threads = {}
        thr_name = "mqtt-sub-listen"
        threads[thr_name] = threading.Thread(None,
                                              self.mqttClient.mqttloop,
                                              thr_name,
                                              (),
                                              {})
        threads[thr_name].start()
        self.register_thread(threads[thr_name])
        
        # Callback for new/update devices
        self.log.info(u"==> Add callback for new/update devices.")
        self.register_cb_update_devices(self.reload_devices)
        
        self.ready()


    # -------------------------------------------------------------------------------------------------
    def setMqttDevicesList(self, devices):
        self.log.info(u"==> Set MQTT devices list ...")
        self.mqttdevices_list = {}  
        self.mqttsubtopics = []                                         # Topics list to subscribe: [("domogik/sensor1/#", 0), ("domogik/sensor2/#", 0)]      
        for a_device in devices:    # For each device
            # self.log.info(u"a_device:   %s" % format(a_device))
            device_topic = self.get_parameter(a_device, "topic")    # Ex.: "sensor/weather/temp"
            device_qos = self.get_parameter(a_device, "qos")        # Ex.: 0
            if "sensor" in a_device["device_type_id"]:  self.mqttsubtopics.append(((str(device_topic) + '/#'), int(device_qos)))        
            self.mqttdevices_list.update(
                {a_device["id"] : 
                    {'name': a_device["name"], 
                     'type' : a_device["device_type_id"], 
                     'topic': device_topic, 
                     'qos' : device_qos
                    }
                })
            self.log.info(u"==> Device MQTT '{0}'" . format(self.mqttdevices_list[a_device["id"]]))
        self.mqttClient.reloadMQTTDevices(self.mqttdevices_list, self.mqttsubtopics)
            
            
    # -------------------------------------------------------------------------------------------------
    def send_pub_data(self, device_id, value):
        """ Send the sensors values over MQ
        """
        data = {}
#        sensor_device = self.sensors[device_id].keys()[0]       # Example: 'sensor_script_info_temperature'
#        data[self.sensors[device_id][sensor_device]] = value    # data['id_sensor'] = value

        for sensor in self.sensors[device_id]:                  #
            data[self.sensors[device_id][sensor]] = value       # sensor = 'sensor name' in info.json file
        self.log.debug(u"==> Update Sensor '%s' for device id %s (%s)" % (format(data), device_id, self.mqttdevices_list[device_id]["name"]))    # {u'id': u'value'}

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
            if device_id not in self.mqttdevices_list:
                self.log.error(u"### MQ REQ command, Device ID '%s' unknown" % device_id)
                status = False
                reason = u"Plugin mqtt: Unknown device ID %d" % device_id
                self.send_rep_ack(status, reason, command_id, "unknown") ;                      # Reply MQ REP (acq) to REQ command
                return

            device_name = self.mqttdevices_list[device_id]["name"]
            self.log.info(u"==> Received for device '%s' MQ REQ command message: %s" % (device_name, format(data)))         # {u'value': u'1', u'command_id': 80, u'device_id': 193}
            
            status, reason = self.mqttClient.pubcmd(self.mqttdevices_list[device_id]["topic"], self.mqttdevices_list[device_id]["qos"], data["value"], device_id)
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


    # -------------------------------------------------------------------------------------------------
    def reload_devices(self, devices):
        """ Called when some devices are added/deleted/updated
        """
        self.log.info(u"==> Reload Device called")
        self.setMqttDevicesList(devices)
        self.devices = devices
        self.sensors = self.get_sensors(devices)


if __name__ == "__main__":
    MQTTManager()
