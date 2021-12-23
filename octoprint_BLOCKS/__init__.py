# coding=utf-8

from __future__ import absolute_import

import os
import socket
import netifaces
import octoprint.plugin
import octoprint.events
import octoprint.plugin.core
from octoprint.events import Events
from octoprint.util.comm import parse_firmware_line
from octoprint.util import RepeatedTimer
from .wifisetup import Wifisetup


class BlocksPlugin(octoprint.plugin.SettingsPlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.StartupPlugin,
                   octoprint.plugin.ProgressPlugin,
                   octoprint.plugin.EventHandlerPlugin,
                   octoprint.plugin.ShutdownPlugin,
                   octoprint.plugin.SimpleApiPlugin):

    def __init__(self):
        self._wifiSetUp = Wifisetup()
        self._AP_result = []
        self._interfaces = []
        self._printer_name = None

    # Executes before the startup
    def on_after_startup(self):
        self._logger.info("Blocks initializing...")
        self._wifi_update = RepeatedTimer(6.0, self.wifiStatus, run_first=True)#, condition = self._wifi_reporting_enabled)
        self._wifi_networks_list = RepeatedTimer(
            7.0, self._available_networks, run_first=True)

        self._wifi_update.start()
        self._wifi_networks_list.start()

    # ~~ Wifi

    def _wifi_reporting_enabled(self):
        # TODO: Pick up this
        if self._printer_name == "":
            return True
        return False

    def get_available_wifi_networks(self):
        return self._wifiSetUp.list_available_networks()

    def get_saved_networks(self):
        return self._wifiSetUp.list_existing_networks()

    def _available_networks(self):
        """Get a list with all the networks from a BSS scan
            and send a notification with that list to any message listeners.

        """
        self._AP_result = []
        self._AP_result = self._wifiSetUp.list_available_networks()
        # Now i need to send this to the web page
        notification = {
            "type": "WifiSetUp",
            "hide": "true",
            "message": self._AP_result
        }
        # Sends a message to any message listeners
        self._plugin_manager.send_plugin_message(
            self._identifier, notification)
        self._logger.debug("Available networks fetched.")

    def setNewWifi(self, _data=None):
        """Set a new wifi connection on the pi
        Args:
            _data (type: dict): A dictionary with the ssid and password of the
                new conection to be made. Defaults to None.
        Returns:
            type: Description of returned object.
            type: None. If the argument _data is None.
        Raises:
            ExceptionName: Why the exception is raised.
        """
        if _data is None:
            return None
        # Get and send the list of available networks to connect
        self._available_networks()
        # Set a new internet connection
        self._wifiSetUp.set_wifi_info(
            _ssid=_data["ip"]["ssid"], _psk=_data["ip"]["psk"])
        _output = self._wifiSetUp.set_wifi_ssid_psk()

        if _output:
            notification = {
                "type": "info",
                "action": "popup",
                "hide": "true",
                "message": "Successfully added %s network" % _data["ip"]["ssid"]
            }
            # Sends a message to any message listeners
            self._plugin_manager.send_plugin_message(
                self._identifier, notification)
            self._logger.info("Successfully added %s network" %
                              _data["ip"]["ssid"])
        else:
            self._logger.info("Error while adding %s network" %
                              _data["ip"]["ssid"])

    def wifiStatus(self):
        """
            Controls the wifi status, sends a wifi signal strength integer to marlin.
        """
        _interface = None
        _ssid = None
        _interface, __ssid = self._wifiSetUp.find_connection()

        self.net_data = {
            "Interface": _interface,
            "Ssid": _ssid,
        }
        if self._connectivity_checker.online:
            # Means we really have internet connection. So either wifi or ethernet i guess
            if _interface is not None and _ssid is not None:
                self._wifiSetUp.get_connection_stats(_stats= self.net_data)
                self._logger.debug("Wifi stats found!")

                self._logger.debug(self.net_data)
                """
                Send the M550 W<value> to the printer

                    value = 4 ---> there is no connection
                    value =[5,8] ----> strenght of the signal
                    value = 9 ----> We are using ethernet/Hotspot
                """
                # At this stage we send the wifi level if the printer is connected
                if self._printer.is_operational():
                    self._printer.commands(
                        "M550 W{}".format(self.net_data["WifiLevel"]))
                    self._logger.debug("Wifi quality level sent.")
            elif _ssid is None:
                # Probably are on Ethernet
                if self._printer.is_operational():
                    self._printer.commands("M550 W9")
                    self._logger.debug("Using ethernet.")
        else:
            if self._printer.is_operational():
                # Only send the information to the printer if we are connected to it
                # We don't have internet and probably are on hotspot if the functionality exists.
                self._logger.debug("No internet, but operational")
                # Report that to the printer
                self._printer.commands("M550 W4")

    # ~~ SimpleApiPlugin

    def get_api_commands(self):
        return dict(
            wifi_SetUp=["ip"]
        )

    def on_api_command(self, command, data):
        if command == "wifi_SetUp":
            self._logger.info("Wifi setup in progress.")
            self.setNewWifi(data)

    # ~~ AssetPlugin mixi

    def get_assets(self):
        # Define your plugin's asset(the folder) files to be automatically included in the
        # core UI here.
        return dict(
            js=["js/BLOCKS.js", "js/jquery-ui.min.js",
                "js/notifications.js", "js/BLOCKS_WebCam.js"],
            css=["css/BLOCKS.css", "css/jquery-ui.css",
                 "css/animations.css", "css/bootstrapElems.min.css", "css/bootstrap-grid.min.css"],
            less=["less/BLOCKS.less"]
        )

    # ~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            # Settings that are saved on machine shutdown
            "themeType": False,
            "Machine_Type": "undefined",
        }

    def on_settings_initialized(self):
        # Get the saved settings
        theme = self._settings.get(["themeType"])
        machine = self._settings.get(["Machine_Type"])
        self._settings.set(["Machine_Type"], machine)
        self._settings.set(["themeType"], theme)
        self._logger.debug("theme = {}".format(theme))

    def on_settings_save(self, data):
        # save settings
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        theme = self._settings.get(["themeType"])
        machine = self._settings.get(["Machine_Type"])

        if 'themeType' in data and data['themeType']:
            self._settings.set(["themeType"], theme)
            self._logger.info("Saving settings.")
        if 'Machine_Type' in data and data['Machine_Type']:
            self._settings.set(["Machine_Type"], machine)
            self._logger.info("Saving settings.")

    # ~~ TemplatePlugin mixin

        # This mixin enables me to inject my own components into the OctoPrint
        # My own templates
        # More information on the dictionaries on:
        # https://docs.octoprint.org/en/master/plugins/mixins.html#templateplugin

    def get_template_configs(self):

        return[
            # Connection wrapper template
            dict(type="sidebar", template="blocks_connectionWrapper.jinja2",
                 custom_bindings=True),
            # My webcam link template
            dict(type="tab", name="WebCam", custom_bindings=False),
            # Custom Notifications template
            dict(type="sidebar", template="blocks_notifications_wrapper.jinja2",
                 custom_bindings=True),
            # Light Dark Theme Switch template
            dict(type="navbar", template="lightDarkSwitch.jinja2",
                 custom_bindings=True),
            # Fullscreen button for webcam template
            dict(type="generic", template="webcambar.jinja2",
                 custom_bindings=True),
            # Wifi set up window template
            dict(type="generic", name="Wifi Set Up", template="wifiWindow_settings.jinja2",
                 custom_bindings=True),
            # No Wifi warning on the navbar template
            dict(type="navbar", template="wifiWarning_navbar.jinja2",
                 custom_bindings=True),
            # Template for my Control module section
            dict(type="generic", template="Blocks_controlViewmodel.jinja2",
                 custom_bindings=True),
            dict(type="generic", template="wifiInfoWindow.jinja2", custom_bindings=True),
        ]

    # ~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return dict(
            BLOCKS=dict(
                displayName=self._plugin_name,
                displayVersion=self._plugin_version,
                # version check: github repository
                type="github_release",
                user="HugoCLSC",
                repo="OctoPrint-BLOCKS",
                current=self._plugin_version,
                # update method: pip
                pip="https://github.com/HugoCLSC/OctoPrint-BLOCKS/archive/{target_version}.zip",
            )
        )

    # ~~ EventHandlerPlugin mixin

    def on_event(self, event, payload):
        # Sends messages to any listeners about certain events
        # All available events on https://docs.octoprint.org/en/master/events/index.html#sec-events

        try:
            if event == Events.STARTUP:
                # SERVER = socket.gethostbyname(socket.gethostname())  # Gets the ip address automatically
                # self._logger.debug(SERVER)
                notification ={
                    "type": "IPaddr",
                    "message": SERVER
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)
            if event == Events.PRINT_STARTED:
                notification = {
                    "action": "popup",
                    "type": "info",
                    "hide": "true",
                    "message": "Print Start, Heating"
                }
                # sends a the message to any listeners with the plugin identification and the notification
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)
            if event == Events.PRINT_FAILED:
                notification = {
                    "action": "popup",
                    "type": "error",
                    "hide": "false",
                    "message": "Print Failed"
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)
            # Everytime an event takes place we will send a message to any message listeners that exist
            if event == Events.CONNECTED:
                notification = {
                    "action": "popup",
                    "type": "info",
                    "hide": "true",
                    "message": event,
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)

            if event == Events.DISCONNECTED:
                notification = {
                    "action": "popup",
                    "type": "info",
                    "hide": "true",
                    "message": event,
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)

            if event == Events.DISCONNECTING:
                self._printer.commands("M550 W4")

            self._logger.info("Notification : {}".format(event))
        except Exception as e:
            self._logger.info("Error on event change notifications: {}".format(e))

    # ~~ ProgressPlugin mixin

    def on_print_progress(self, storage, path, progress):
        # Sends a message to any listeners about the print progress
        if progress == 25 or \
           progress == 50 or \
           progress == 75 or \
           progress == 100:
            notification = {
                "action": "popup",
                "type": "warning",
                "hide": "true",
                "message": "Print Progress: {}".format(progress)
            }
            # Sends a message to any message listeners
            self._plugin_manager.send_plugin_message(
                self._identifier, notification)

        self._logger.debug("Print Progress: {}".format(progress))

    def sent_m600(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        try:
            # Everytime i send the commands M701 and M702 this function will trigger
            # Possible because of the hook "octoprint.comm.protocol.gcode.sent"
            # M701 'Load Filament'
            # M702 'Unload Filament'
            if gcode and "M600" in gcode:
                notification = {
                    "action": "popup",
                    "type": "warning",
                    "hide": "false",
                    "message": "Filament Change in Progress. Follow the printer instructions"
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)
                self._logger.info(
                    "Notifications: Gcode sent {}".format("gcode"))
        except Exception as e:
            self._logger.info("Error on M600 send: {}".format(e))

    def detect_commands(self, comm, line, *args, **kwargs):
        try:
            if "MACHINE_TYPE" in line:
                printer_data = parse_firmware_line(line)
                self._printer_name = printer_data["MACHINE_TYPE"]
                notification = {
                    "type": "machine_info",
                    "hide": "false",
                    "message": printer_data["MACHINE_TYPE"]
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)

            elif "M412" in line:
                notification = {
                    "action": "popup",
                    "type": "machine_info",
                    "message": "Filament Runout, Change Filament to proceed",
                    "hide": "false",
                }
                self._plugin_manager.send_plugin_message(
                    self._identifier, notification)
            else:
                return line
        except Exception as e:
            self._logger.info("Detect Machine type and Filament Runout error: {}".format(e))


__plugin_name__ = "Blocks"
__plugin_pythoncompat__ = ">=3.3,<4"
__plugin_license__ = "AGPLv3"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = BlocksPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.sent_m600,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.detect_commands,
    }
