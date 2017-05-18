# -*- coding: utf-8 -*-

### common imports
from flask import Blueprint, abort
from domogik.common.utils import get_packages_directory
from domogik.admin.application import render_template
from domogik.admin.views.clients import get_client_detail, get_client_devices
from jinja2 import TemplateNotFound
from datetime import datetime
### package specific imports
import subprocess


def get_informations(devices):
    sensorslist = []
    for a_device in devices:
        for a_sensor in a_device["sensors"]:
            sensorslist.append({"device": a_device["name"], 
                                "name": a_device["sensors"][a_sensor]["name"],                                 
                                "reference": a_device["sensors"][a_sensor]["reference"], 
                                "date":  datetime.fromtimestamp(a_device["sensors"][a_sensor]["last_received"]).strftime("%e %b %k:%M"), 
                                "value": a_device["sensors"][a_sensor]["last_value"], 
                                "type": a_device["sensors"][a_sensor]["data_type"] 
                                })
    return sensorslist

    
### package specific functions
def get_errorlog(log):
    print("Log file = %s" % log)
    errorlog = subprocess.Popen(['/bin/egrep', 'ERROR|WARNING', log], stdout=subprocess.PIPE)
    output = errorlog.communicate()[0]
    if not output:
        output = "No ERROR or WARNING"
    if isinstance(output, str):
        output = unicode(output, 'utf-8')
    return output


### common tasks
package = "plugin_mqtt"
template_dir = "{0}/{1}/admin/templates".format(get_packages_directory(), package)
static_dir = "{0}/{1}/admin/static".format(get_packages_directory(), package)
logfile = "/var/log/domogik/{0}.log".format(package)

plugin_mqtt_adm = Blueprint(package, __name__,
                        template_folder = template_dir,
                        static_folder = static_dir)


@plugin_mqtt_adm.route('/<client_id>')
def index(client_id):

    detail = get_client_detail(client_id)       # mqtt plugin configuration
    devices = get_client_devices(client_id)     # mqtt plugin devices list
    try:
        return render_template('plugin_mqtt.html',
            clientid = client_id,
            client_detail = detail,
            mactive="clients",
            active = 'advanced',
            sensorslist = get_informations(devices),
            errorlog = get_errorlog(logfile))

    except TemplateNotFound:
        abort(404)


@plugin_mqtt_adm.route('/<client_id>/log')
def log(client_id):
    clientid = client_id
    detail = get_client_detail(client_id)
    with open(logfile, 'r') as contentLogFile:
        content_log = contentLogFile.read()
        if not content_log:
            content_log = "Empty log file"
        if isinstance(content_log, str):
            content_log = unicode(content_log, 'utf-8')
    try:
        return render_template('plugin_mqtt_log.html',
            clientid = client_id,
            client_detail = detail,
            mactive="clients",
            active = 'advanced',
            logfile = logfile,
            contentLog = content_log)

    except TemplateNotFound:
        abort(404)
