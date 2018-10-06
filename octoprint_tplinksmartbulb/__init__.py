# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.server import user_permission
import socket
import json
import logging
import os
import re
import threading
import time
from datetime import datetime

class tplinksmartbulbPlugin(octoprint.plugin.SettingsPlugin,
                            octoprint.plugin.AssetPlugin,
                            octoprint.plugin.TemplatePlugin,
							octoprint.plugin.SimpleApiPlugin,
							octoprint.plugin.StartupPlugin):
							
	def __init__(self):
		self._logger = logging.getLogger("octoprint.plugins.tplinksmartbulb")
		self._tplinksmartbulb_logger = logging.getLogger("octoprint.plugins.tplinksmartbulb.debug")
							
	##~~ StartupPlugin mixin
	
	def on_startup(self, host, port):
		# setup customized logger
		from octoprint.logging.handlers import CleaningTimedRotatingFileHandler
		tplinksmartbulb_logging_handler = CleaningTimedRotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="debug"), when="D", backupCount=3)
		tplinksmartbulb_logging_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
		tplinksmartbulb_logging_handler.setLevel(logging.DEBUG)

		self._tplinksmartbulb_logger.addHandler(tplinksmartbulb_logging_handler)
		self._tplinksmartbulb_logger.setLevel(logging.DEBUG if self._settings.get_boolean(["debug_logging"]) else logging.INFO)
		self._tplinksmartbulb_logger.propagate = False
	
	def on_after_startup(self):
		self._logger.info("TPLinkSmartBulb loaded!")
	
	##~~ SettingsPlugin mixin
	
	def get_settings_defaults(self):
		return dict(
			debug_logging = False,
			arrSmartBulbs = [{'ip':'','label':'','icon':'icon-lightbulb','displayWarning':True,'warnPrinting':False,'gcodeEnabled':False,'gcodeOnDelay':0,'gcodeOffDelay':0,'autoConnect':True,'autoConnectDelay':10.0,'autoDisconnect':True,'autoDisconnectDelay':0,'sysCmdOn':False,'sysRunCmdOn':'','sysCmdOnDelay':0,'sysCmdOff':False,'sysRunCmdOff':'','sysCmdOffDelay':0,'currentState':'unknown','btnColor':'#808080'}],
			pollingInterval = 15,
			pollingEnabled = False
		)
		
	def on_settings_save(self, data):	
		old_debug_logging = self._settings.get_boolean(["debug_logging"])

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

		new_debug_logging = self._settings.get_boolean(["debug_logging"])
		if old_debug_logging != new_debug_logging:
			if new_debug_logging:
				self._tplinksmartbulb_logger.setLevel(logging.DEBUG)
			else:
				self._tplinksmartbulb_logger.setLevel(logging.INFO)
				
	def get_settings_version(self):
		return 1
		
	def on_settings_migrate(self, target, current=None):
		if current is None or current < self.get_settings_version():
			# Reset bulb settings to defaults.
			self._logger.debug("Resetting arrSmartBulbs for tplinksmartbulb settings.")
			self._settings.set(['arrSmartBulbs'], self.get_settings_defaults()["arrSmartBulbs"])
		
	##~~ AssetPlugin mixin

	def get_assets(self):
		return dict(
			js=["js/tplinksmartbulb.js","js/knockout-bootstrap.min.js"],
			css=["css/tplinksmartbulb.css"]
		)
		
	##~~ TemplatePlugin mixin
	
	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=True),
			dict(type="settings", custom_bindings=True)
		]
		
	##~~ SimpleApiPlugin mixin
	
	def turn_on(self, bulbip):
		self._tplinksmartbulb_logger.debug("Turning on %s." % bulbip)
		bulb = self.bulb_search(self._settings.get(["arrSmartBulbs"]),"ip",bulbip)
		self._tplinksmartbulb_logger.debug(bulb)
		chk = self.sendCommand('{"smartlife.iot.smartbulb.lightingservice":{"transition_light_state":{"on_off":1}}}',bulbip)["smartlife.iot.smartbulb.lightingservice"]["err_code"]
			
		if chk == 0:
			self.check_status(bulbip)
			if bulb["autoConnect"]:
				c = threading.Timer(int(bulb["autoConnectDelay"]),self._printer.connect)
				c.start()
			if bulb["sysCmdOn"]:
				t = threading.Timer(int(bulb["sysCmdOnDelay"]),os.system,args=[bulb["sysRunCmdOn"]])
				t.start()
	
	def turn_off(self, bulbip):
		self._tplinksmartbulb_logger.debug("Turning off %s." % bulbip)
		bulb = self.bulb_search(self._settings.get(["arrSmartBulbs"]),"ip",bulbip)
		self._tplinksmartbulb_logger.debug(bulb)
		
		if bulb["sysCmdOff"]:
			t = threading.Timer(int(bulb["sysCmdOffDelay"]),os.system,args=[bulb["sysRunCmdOff"]])
			t.start()
		if bulb["autoDisconnect"]:
			self._printer.disconnect()
			time.sleep(int(bulb["autoDisconnectDelay"]))
			
		chk = self.sendCommand('{"smartlife.iot.smartbulb.lightingservice":{"transition_light_state":{"on_off":0}}}',bulbip)["smartlife.iot.smartbulb.lightingservice"]["err_code"]
			
		if chk == 0:
			self.check_status(bulbip)
		
	def check_status(self, bulbip):
		self._tplinksmartbulb_logger.debug("Checking status of %s." % bulbip)
		if bulbip != "":
			response = self.sendCommand('{"system":{"get_sysinfo":{}}}', bulbip)
			self._tplinksmartbulb_logger.info(response)
				
			chk = self.lookup(response,*["system","get_sysinfo","light_state","on_off"])
			if chk == 1:
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="on",ip=bulbip))
			elif chk == 0:
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="off",ip=bulbip))
			else:
				self._tplinksmartbulb_logger.debug(response)
				self._plugin_manager.send_plugin_message(self._identifier, dict(currentState="unknown",ip=bulbip))
	
	def get_api_commands(self):
		return dict(turnOn=["ip"],turnOff=["ip"],checkStatus=["ip"])

	def on_api_command(self, command, data):
		if not user_permission.can():
			from flask import make_response
			return make_response("Insufficient rights", 403)
        
		if command == 'turnOn':
			self.turn_on("{ip}".format(**data))
		elif command == 'turnOff':
			self.turn_off("{ip}".format(**data))
		elif command == 'checkStatus':
			self.check_status("{ip}".format(**data))
			
	##~~ Utilities
	
	def rgb2hsv(self, r, g, b):
		r, g, b = r/255.0, g/255.0, b/255.0
		return_val = dict()
		mx = max(r, g, b)
		mn = min(r, g, b)
		df = mx-mn
		if mx == mn:
			return_val["hue"] = 0
		elif mx == r:
			return_val["hue"] = (60 * ((g-b)/df) + 360) % 360
		elif mx == g:
			return_val["hue"] = (60 * ((b-r)/df) + 120) % 360
		elif mx == b:
			return_val["hue"] = (60 * ((r-g)/df) + 240) % 360
		if mx == 0:
			return_val["saturation"] = 0
		else:
			return_val["saturation"] = df/mx * 100
		return_val["value"] = mx
		return return_val
	
	def lookup(self, dic, key, *keys):
		if keys:
			return self.lookup(dic.get(key, {}), *keys)
		return dic.get(key)
	
	def bulb_search(self, list, key, value): 
		for item in list: 
			if item[key] == value: 
				return item
	
	def encrypt(self, string):
		key = 171
		result = "\0\0\0"+chr(len(string))
		for i in string: 
			a = key ^ ord(i)
			key = a
			result += chr(a)
		return result

	def decrypt(self, string):
		key = 171 
		result = ""
		for i in string: 
			a = key ^ ord(i)
			key = ord(i) 
			result += chr(a)
		return result
	
	def sendCommand(self, cmd, bulbip):
		commands = {'info'     : '{"system":{"get_sysinfo":{}}}',
			'on'       : '{"system":{"set_relay_state":{"state":1}}}',
			'off'      : '{"system":{"set_relay_state":{"state":0}}}',
			'cloudinfo': '{"cnCloud":{"get_info":{}}}',
			'wlanscan' : '{"netif":{"get_scaninfo":{"refresh":0}}}',
			'time'     : '{"time":{"get_time":{}}}',
			'schedule' : '{"schedule":{"get_rules":{}}}',
			'countdown': '{"count_down":{"get_rules":{}}}',
			'antitheft': '{"anti_theft":{"get_rules":{}}}',
			'reboot'   : '{"system":{"reboot":{"delay":1}}}',
			'reset'    : '{"system":{"reset":{"delay":1}}}'
		}
		
		# try to connect via ip address
		try:
			socket.inet_aton(bulbip)
			ip = bulbip
			self._tplinksmartbulb_logger.debug("IP %s is valid." % bulbip)
		except socket.error:
		# try to convert hostname to ip
			self._tplinksmartbulb_logger.debug("Invalid ip %s trying hostname." % bulbip)
			try:
				ip = socket.gethostbyname(bulbip)
				self._tplinksmartbulb_logger.debug("Hostname %s is valid." % bulbip)
			except (socket.herror, socket.gaierror):
				self._tplinksmartbulb_logger.debug("Invalid hostname %s." % bulbip)
				return {"system":{"get_sysinfo":{"relay_state":3}}}
				
		try:
			sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock_tcp.connect((ip, 9999))
			sock_tcp.send(self.encrypt(cmd))
			data = sock_tcp.recv(2048)
			sock_tcp.close()
			
			self._tplinksmartbulb_logger.debug("Sending command %s to %s" % (cmd,bulbip))
			self._tplinksmartbulb_logger.debug(self.decrypt(data))
			return json.loads(self.decrypt(data[4:]))
		except socket.error:
			self._tplinksmartbulb_logger.debug("Could not connect to %s." % bulbip)
			return {"system":{"get_sysinfo":{"relay_state":3}}}
			
	##~~ Gcode processing hook
	
	def gcode_turn_off(self, bulb):
		if bulb["warnPrinting"] and self._printer.is_printing():
			self._logger.info("Not powering off %s because printer is printing." % bulb["label"])
		else:
			self.turn_off(bulb["ip"])
	
	def processGCODE(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):				
		workcmd = cmd.upper()

		if gcode:		
			if workcmd.startswith("M80"):			
				bulbip = re.sub(r'^M80\s?', '', workcmd)
				self._tplinksmartbulb_logger.debug("Received M80 command, attempting power on of %s." % bulbip)
				bulb = self.bulb_search(self._settings.get(["arrSmartBulbs"]),"ip",bulbip)
				self._tplinksmartbulb_logger.debug(bulb)
				if bulb["gcodeEnabled"]:
					t = threading.Timer(int(bulb["gcodeOnDelay"]),self.turn_on,args=[bulbip])
					t.start()
				return
			elif workcmd.startswith("M81"):
				bulbip = re.sub(r'^M81\s?', '', workcmd)
				self._tplinksmartbulb_logger.debug("Received M81 command, attempting power off of %s." % bulbip)
				bulb = self.bulb_search(self._settings.get(["arrSmartBulbs"]),"ip",bulbip)
				self._tplinksmartbulb_logger.debug(bulb)
				if bulb["gcodeEnabled"]:
					t = threading.Timer(int(bulb["gcodeOffDelay"]),self.gcode_turn_off,[bulb])
					t.start()
				return
			elif workcmd.startswith("M150"):
				workleds = dict()
				workval = workcmd.split()
				for i in workval:
					firstchar = str(i[0].upper())
					leddata = str(i[1:].strip())
					if not leddata.isdigit() and firstchar != 'I':
						self._tplinksmartbulb_logger.debug(leddata)
						return

					if firstchar == 'M':
						continue
					elif firstchar == "I":
						bulbip = leddata
					elif firstchar == 'R':
						workleds['LEDRed'] = int(leddata)
					elif firstchar == 'B':
						workleds['LEDBlue'] = int(leddata)
					elif firstchar == 'G' or firstchar == 'U':
						workleds['LEDGreen'] = int(leddata)
					elif firstchar == "W":
						workleds['LEDWhite'] = int(leddata)
					elif firstchar == "P":
						workleds['LEDBrightness'] = int(leddata)
					else:
						self._tplinksmartbulb_logger.debug(leddata)

				bulb = self.bulb_search(self._settings.get(["arrSmartBulbs"]),"ip",bulbip)
				self._tplinksmartbulb_logger.debug("Received M150 command, attempting color change of %s." % bulbip)
				self._tplinksmartbulb_logger.debug(workleds)
				if bulb["gcodeEnabled"]:
					led_hsv = self.rgb2hsv(workleds['LEDRed'], workleds['LEDGreen'], workleds['LEDBlue'])
					chk = self.sendCommand('{"smartlife.iot.smartbulb.lightingservice":{"transition_light_state":{"saturation":%d,"brightness":%d,"mode":"normal","color_temp":%d,"hue":%d,"transition_period":3000}}}' % (led_hsv['saturation'],int(workleds['LEDBrightness']/255),led_hsv['value'],led_hsv['hue']),bulbip)
					self._tplinksmartbulb_logger.debug(chk)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
			tplinksmartbulb=dict(
				displayName="TP-Link SmartBulb",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="jneilliii",
				repo="OctoPrint-TPLinkSmartBulb",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/jneilliii/OctoPrint-TPLinkSmartBulb/archive/{target_version}.zip"
			)
		)


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "TP-Link SmartBulb"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = tplinksmartbulbPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.processGCODE,
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

