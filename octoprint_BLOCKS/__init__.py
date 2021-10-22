# coding=utf-8

from __future__ import absolute_import

import octoprint.plugin
import octoprint.events
import octoprint.util.comm
import octoprint.plugin.core
from octoprint.events import Events
from octoprint.util.comm import parse_firmware_line
from octoprint.util import RepeatedTimer

from .python3wifi.iwlibs import Wireless, getWNICnames, getNICnames



class BlocksPlugin(octoprint.plugin.SettingsPlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.StartupPlugin,
                   octoprint.plugin.ProgressPlugin,
                   octoprint.plugin.EventHandlerPlugin,
                   octoprint.plugin.ShutdownPlugin):


    #Try this
    def __init__(self):
        # This variable is just so i can see if we are using wifi or not
        # Initially set to True because we assume we are on wifi when we startup
        self._wifi = True

    # Exceutes before the startup
    def on_after_startup(self):
        self._logger.info("Blocks initializing...")
        self._wifi_update = RepeatedTimer(10.0, self._wifi_status, condition = self._wifi_flag )
        self._wifi_update.start()

    # ~~ Wifi

    def update_interface_list(self):
        self._interfaces = []
        try:
            # Gets all the names of the interfaces available
            for interface in getWNICnames():
                self._interfaces.append(interface)
        except:
            pass

    def _wifi_flag(self):
        return self._wifi

    def _wifi_strength_calc(self, signalLevel):
        _level = 0

        if signalLevel is None or signalLevel <= 10:
            _level = 2
        elif signalLevel > 10 and signalLevel <= 25:
            _level = 3
        elif signalLevel > 25 and signalLevel <= 50:
            _level = 4
        elif signalLevel > 50 and signalLevel <= 85:
            _level = 5
        elif signalLevel > 85 and signalLevel <= 100:
            _level = 6

        return _level

    def _wifi_status(self):
        _interface = None
        _ssid = None
        if self._wifi == True:
            self.update_interface_list()
        else:
            # Means we are on ethernet
            _internet = "eth0"

        for _interface in self._interfaces:
            if _interface is not None:
                try:
                    wifi = Wireless(_interface)
                    _ssid = wifi.getEssid()
                    if _ssid:
                        break
                except:
                    pass

        if _ssid is None and self._wifi == True:
            self._wifi = False
        elif _ssid is None and self._wifi == False:
            # This means that not even the ethernet works
            # But we don't need to do anything here 

        self.net_data = {
            "Interface": _interface,
            "Ssid": _ssid,
        }
        if self._wifi == True:
            if _interface is not None and _ssid is not None:
                _,quality,_,_ = wifi.getStatistics()
                self.net_data["Quality"] = quality.quality
                self.net_data["Signal"] = quality.siglevel
                self._logger.info("Wifi stats found.")

            self._logger.info(self._interfaces)
            self._logger.info(self.net_data)
            """
            Send the M550 W<value> to the printer

                value = 2 ---> there is no connection
                value =[3,6] ----> strenght of the signal
            """
            _level = self._wifi_strength_calc(self.net_data["Quality"])
            # At this stage we send the wifi level
            if self._printer.is_operational():
                self._logger.info("Wifi quality sent")
                self._printer.commands("M550 W{}".format(_level))

        elif self._wifi == False:
            if self._printer.is_operational():
                self._logger.info("We are on ethernet")
                self._printer.commands("M550 W7")


    # def on_shutdown(self):
    #     self._printer.commands("M550 W2")

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
            # For Light and Dark Theme
            # The default is the Light Theme
            "themeType": False,
            "Machine_Type": "undefined"
        }

    def on_settings_initialized(self):
        # Get the saved settings
        theme = self._settings.get(["themeType"])
        machine = self._settings.get(["Machine_Type"])
        self._settings.set(["Machine_Type"], machine)
        self._settings.set(["themeType"], theme)
        self._logger.info("theme = {}".format(theme))

    def on_settings_save(self, data):
        # save settings
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        theme = self._settings.get(["themeType"])
        machine = self._settings.get(["Machine_Type"])
        if 'themeType' in data and data['themeType']:
            self._settings.set(["themeType"], theme)
            self.logger.info("Saving settings.")
        if 'Machine_Type' in data and data['Machine_Type']:
            self._settings.set(["Machine_Type"], machine)
            self.logger.info("Saving settings.")

    # ~~ TemplatePlugin mixin

        # This mixin enables me to inject my own components into the OctoPrint
        # My own templates
        # More information on the dictionaries on:
        # https://docs.octoprint.org/en/master/plugins/mixins.html#templateplugin

    def get_template_configs(self):

        return[
            dict(type="settings", custom_bindings=False),
            # Connection wrapper
            dict(type="sidebar", template="blocks_connectionWrapper.jinja2",
                 custom_bindings=True),
            # My webcam link
            dict(type="tab", name="WebCam", template="webcam_tab.jinja2",
                 custom_bindings=False),
            # Fan slider
            dict(type="generic", template="fanSlider.jinja2", custom_bindings=True),
            # Custom Notifications
            dict(type="sidebar", template="blocks_notifications_wrapper.jinja2",
                 custom_bindings=True),
            # For Load Unload functions on the control section
            dict(type="generic", template="changeFilament.jinja2",
                 custom_bindings=True),
            # Light Dark Theme Switch
            dict(type="navbar", template="lightDarkSwitch.jinja2",
                 custom_bindings=True),
            dict(type="generic", template="webcambar.jinja2", custom_bindings=True)
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
                repo="BLOCKSUI",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/HugoCLSC/BLOCKSUI/archive/{target_version}.zip",
            )
        )

    # ~~ EventHandlerPlugin mixin

    def on_event(self, event, payload):
        # Sends messages to any listeners about certain events
        # All available events on https://docs.octoprint.org/en/master/events/index.html#sec-events

        try:
            if event == Events.STARTUP:
                SERVER = socket.gethostbyname(socket.gethostname()) #Gets the ip address automatically
                self._logger.info(SERVER)
                notification={
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
                self._printer.commands("M550 W2")

            self._logger.info("Notification : {}".format(event))
        except Exception as e:
            self._logger.info(e)

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

        self._logger.info("Print Progress: {}".format(progress))

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
            self._logger.info(e)

    def detect_commands(self, comm, line, *args, **kwargs):
        try:
            if "MACHINE_TYPE" in line:
                printer_data = parse_firmware_line(line)
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
            self._logger.info(e)



__plugin_name__ = "Blocks Plugin"
__plugin_pythoncompat__ = ">=2.7,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = BlocksPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.sent_m600,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.detect_commands,
    }
