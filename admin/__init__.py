# -*- coding: utf-8 -*-

### common imports
from flask import Blueprint, abort, flash, request
from domogik.common.utils import get_packages_directory, get_libraries_directory
from domogik.admin.application import render_template
from domogik.admin.views.clients import get_client_detail, get_client_devices
from jinja2 import TemplateNotFound
from datetime import datetime
### package specific imports
import subprocess
import json
import zmq
from zmq.eventloop.ioloop import IOLoop
from domogikmq.reqrep.client import MQSyncReq
from domogikmq.message import MQMessage

try:
    from flask.ext.babel import gettext, ngettext
except ImportError:
    from flask_babel import gettext, ngettext
    pass


# -------------------------------------------------------------------------------------------------
def get_sensors(devices):
    sensorslist = []
    for a_device in devices:
        for a_sensor in a_device["sensors"]:
            if a_device["sensors"][a_sensor]["last_received"]:
                last_received = datetime.fromtimestamp(a_device["sensors"][a_sensor]["last_received"]).strftime("%e %b %k:%M")
            else:
                last_received = ""
            stype = a_device["sensors"][a_sensor]["data_type"]
            value = a_device["sensors"][a_sensor]["last_value"]
            sensorid = a_device["sensors"][a_sensor]["id"]
            sensorslist.append({"device": a_device["name"], 
                                "type": stype.replace("DT_", ""),
                                "date": last_received, 
                                "value": value,
                                "id": sensorid
                                })
    return sensorslist

# -------------------------------------------------------------------------------------------------
def get_commands(devices):
    commandslist = []
    for a_device in devices:
        for a_command in a_device["commands"]:
            stype = a_device["commands"][a_command]["parameters"][0]["data_type"]
            key = a_device["commands"][a_command]["parameters"][0]["key"]
            commandid = a_device["commands"][a_command]["id"]
            commandslist.append({"device": a_device["name"], 
                                "type": stype.replace("DT_", ""),
                                "key": key,
                                "id": commandid
                                })
    return commandslist

# -------------------------------------------------------------------------------------------------
def is_dtparent(dt, parent):
    ''' Return 'True' if dt is part of parent type
    '''
    if dt == parent: return True
    datatypenamefile = lib_dir + "/resources/datatypes.json"
    datatypes = json.load(open(datatypenamefile))
    if "parent" in datatypes[dt]:
        return True if datatypes[dt]["parent"] == parent else False
    else:
        return False
        
# -------------------------------------------------------------------------------------------------
def get_errorlog(log):
    print("Log file = %s" % log)
    errorlog = subprocess.Popen(['/bin/egrep', 'ERROR|WARNING', log], stdout=subprocess.PIPE)
    output = errorlog.communicate()[0]
    if not output:
        output = "No ERROR or WARNING"
    if isinstance(output, str):
        output = unicode(output, 'utf-8')
    return output


# -------------------------------------------------------------------------------------------------
### common tasks
# -------------------------------------------------------------------------------------------------
package = "plugin_mqtt"
template_dir = "{0}/{1}/admin/templates".format(get_packages_directory(), package)
static_dir = "{0}/{1}/admin/static".format(get_packages_directory(), package)
lib_dir = get_libraries_directory()
logfile = "/var/log/domogik/{0}.log".format(package)

plugin_mqtt_adm = Blueprint(package, __name__,
                        template_folder = template_dir,
                        static_folder = static_dir)

cli = MQSyncReq(zmq.Context())
msg = MQMessage()
msg.set_action('datatype.get')
res = cli.request('manager', msg.get(), timeout=10)
if res is not None:
    datatypeslist = res.get_data()['datatypes']
else:
    datatypeslist = {}

# -------------------------------------------------------------------------------------------------
@plugin_mqtt_adm.route('/<client_id>')
def index(client_id):

    detail = get_client_detail(client_id)       # mqtt plugin configuration
    devices = get_client_devices(client_id)     # mqtt plugin devices list
    #print("\n\nget_client_devices = \n%s\n\n" % format(devices))
    
    try:
        return render_template('plugin_mqtt.html',
            clientid = client_id,
            client_detail = detail,
            mactive = "clients",
            active = 'advanced',
            datatypes = datatypeslist,
            rest_url = request.url_root + "rest",
            sensorslist = get_sensors(devices),
            commandslist = get_commands(devices),
            logfile = logfile, 
            errorlog = get_errorlog(logfile))

    except TemplateNotFound:
        abort(404)


# -------------------------------------------------------------------------------------------------
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
            mactive = "clients",
            active = 'advanced',
            logfile = logfile,
            contentLog = content_log)

    except TemplateNotFound:
        abort(404)


# -------------------------------------------------------------------------------------------------
@plugin_mqtt_adm.route('/<client_id>/<sensor_id>/<device>/<stype>/graph')
def graph(client_id, sensor_id, device, stype):
    flash(gettext(u"Loading data"), "info")

    clientid = client_id
    detail = get_client_detail(client_id)
    
    if sensor_id == '0':
        flash(gettext(u"No data to graph"), "error")
        abort(404)
    
    tsfrom = int(datetime.now().strftime("%s")) - 2678400       # now - 32d
    datahistory = []
    
    cli = MQSyncReq(zmq.Context())
    msg = MQMessage()
    msg.set_action('sensor_history.get')
    msg.add_data('sensor_id', sensor_id)
    msg.add_data('mode', 'period')
    msg.add_data('from', tsfrom) 
    
    sensor_history = cli.request('admin', msg.get(), timeout=15).get()
    if 'sensor_history.result' in sensor_history:
        historyvalues = json.loads(sensor_history[1])
        if historyvalues["status"]:
            for value in historyvalues["values"]:
                datahistory.append([value["timestamp"] * 1000, value["value_num"]])
                
    try:
        stypeunit = datatypeslist["DT_" + stype]['unit']
    except KeyError:
        stypeunit = ""

    try:
        return render_template('plugin_mqtt_graph.html',
            clientid = client_id,
            client_detail = detail,
            mactive = "clients",
            active = 'advanced',
            device = device,
            stype = stype,
            unit = stypeunit,
            data = datahistory)

    except TemplateNotFound:
        abort(404)
