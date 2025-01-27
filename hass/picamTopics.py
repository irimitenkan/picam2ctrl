'''
Created on 24.04.2024

@author: irimi
'''
from hass import MQTTClient as hass
import logging
from config import CheckConfig

TIMER_MIN = 1
CNT_MIN = 0

class TP:
    REC = "Recording"
    SNAP = "Snapshot"
    SNAPCNT = "SnapCounter"
    SNAPTI = "SnapTimer"
    VIDEO = "Video"
    VIDEOTI = "VideoTimer"
    VIDSPEED = "VidLapseSpeed"
    HTTP = "HttpStream"
    RTSP = "RtspStream"
    TIMELAPSE = "TimeLapse"
    UDP = "UdpStream"
    MOTION = "Motion"
    MOTION_EN = "MotionEnabled"
    PAN = "Pan"
    TILT = "Tilt"
    PANA = "PanAutomation"
    LSENS = "Lightsensor"
    TUNECTRLS = "TuneCtrls"
    TUNE_AWBEN = "AwbEnable"
    TUNE_AWBMODE = "AwbMode"
    TUNE_BRIGHT = "Brightness"
    TUNE_CONTRAST = "Contrast"
    TUNE_SAT = "Saturation"
    TUNE_SHARP = "Sharpness"

    clientTopics = {REC: hass.HASS_COMPONENT_BINARY_SENSOR,
                    SNAP: hass.HASS_COMPONENT_SWITCH,
                    SNAPTI: hass.HASS_COMPONENT_NUMBER,
                    SNAPCNT: hass.HASS_COMPONENT_NUMBER,
                    VIDEO: hass.HASS_COMPONENT_SWITCH,
                    VIDEOTI: hass.HASS_COMPONENT_NUMBER,
                    VIDSPEED: hass.HASS_COMPONENT_NUMBER,
                    TIMELAPSE: hass.HASS_COMPONENT_SWITCH,
                    HTTP: hass.HASS_COMPONENT_SWITCH,
                    RTSP: hass.HASS_COMPONENT_SWITCH,
                    UDP: hass.HASS_COMPONENT_SWITCH,
                    MOTION_EN: hass.HASS_COMPONENT_SWITCH,
                    MOTION: hass.HASS_COMPONENT_BINARY_SENSOR,
                    PANA: hass.HASS_COMPONENT_SWITCH,
                    PAN: hass.HASS_COMPONENT_NUMBER,
                    TILT: hass.HASS_COMPONENT_NUMBER,
                    LSENS: hass.HASS_COMPONENT_SENSOR,

                    TUNECTRLS : hass.HASS_COMPONENT_SWITCH,
                    TUNE_AWBEN : hass.HASS_COMPONENT_SWITCH,
                    TUNE_AWBMODE : hass.HASS_COMPONENT_SELECT,
                    TUNE_BRIGHT : hass.HASS_COMPONENT_NUMBER,
                    TUNE_CONTRAST : hass.HASS_COMPONENT_NUMBER,
                    TUNE_SAT : hass.HASS_COMPONENT_NUMBER,
                    TUNE_SHARP : hass.HASS_COMPONENT_NUMBER

                    }


    def __init__(self,cfg):
        self.cfg = cfg
        self.defaults ={
            TP.REC : False,
            TP.SNAP : hass.HASS_STATE_ON if self.cfg.startup.snap else hass.HASS_STATE_OFF,
            TP.SNAPCNT : self.cfg.startup.SnapCount, #0 = endless
            TP.SNAPTI : self.cfg.startup.SnapTimer,
            TP.VIDEO : hass.HASS_STATE_ON if self.cfg.startup.video else hass.HASS_STATE_OFF,
            TP.VIDEOTI : self.cfg.startup.VideoTimer,
            TP.VIDSPEED : self.cfg.startup.VideoLapseSpeed,
            TP.HTTP : hass.HASS_STATE_ON if self.cfg.startup.httpStream else hass.HASS_STATE_OFF,
            TP.RTSP : hass.HASS_STATE_ON if self.cfg.startup.rtspStream else hass.HASS_STATE_OFF,
            TP.TIMELAPSE : hass.HASS_STATE_ON if self.cfg.startup.videolapse else hass.HASS_STATE_OFF,
            TP.UDP : hass.HASS_STATE_ON if self.cfg.startup.udpStream else hass.HASS_STATE_OFF,
            TP.MOTION : False,
            TP.MOTION_EN : hass.HASS_STATE_ON if self.cfg.startup.motion else hass.HASS_STATE_OFF,
            TP.PAN : hass.HASS_STATE_OFF,
            TP.TILT : hass.HASS_STATE_OFF,
            TP.PANA : hass.HASS_STATE_OFF,
            TP.LSENS : 0,
            TP.TUNECTRLS : hass.HASS_STATE_ON if self.cfg.camera.CtrlsEnabled else hass.HASS_STATE_OFF,
            }

        self.TuneCtrls={
            TP.TUNE_AWBEN : True if self.cfg.camera.Tune.AwbEnable else False,
            TP.TUNE_AWBMODE : self.cfg.camera.Tune.AwbMode,
            TP.TUNE_BRIGHT : self.cfg.camera.Tune.Brightness,
            TP.TUNE_CONTRAST : self.cfg.camera.Tune.Contrast,
            TP.TUNE_SAT : self.cfg.camera.Tune.Saturation,
            TP.TUNE_SHARP : self.cfg.camera.Tune.Sharpness
            }

        self.TuneCtrlsDigits=[
            TP.TUNE_BRIGHT,
            TP.TUNE_CONTRAST,
            TP.TUNE_SAT,
            TP.TUNE_SHARP
            ]

        self.defaults.update(self.TuneCtrls)

    def getInitNonAvail(self):

        na = []
        if hass.HASS_STATE_OFF==self.defaults[TP.MOTION_EN]:
            na.append(TP.MOTION)
        logging.debug(f"na={na}")
        return na

    def setInitValues(self,buffer:dict):
        for tp in buffer:
            if tp in self.defaults:
                buffer[tp]=self.defaults[tp]
            else:
                logging.error(f"class TP unknown defaults[{tp}]")

    def getClientTopics(self) -> dict :

        tps=dict(self.clientTopics)
        return self.removeTpsByHW(tps)

    def removeTpsByHW(self,tps:dict) -> dict:
        """
        remove topics again if HW not available and not defined in json.cfg
        """
        if not CheckConfig.HasTilt(self.cfg):
            del tps[TP.TILT]
        if not CheckConfig.HasPanTilt(self.cfg):
            del tps[TP.PAN]
            del tps[TP.PANA]
        if not CheckConfig.HasLightSens(self.cfg):
            del tps[TP.LSENS]

        return tps


    def getHassConfigs(self,subTopics):

        hassconfigs = {
            TP.REC: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_RUNNING,
                     hass.HASS_CONFIG_PAYLOAD_ON : True,
                     hass.HASS_CONFIG_PAYLOAD_OFF : False},
            TP.SNAP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                      hass.HASS_CONFIG_ICON:"mdi:camera"},
            TP.TIMELAPSE:{hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                          hass.HASS_CONFIG_ICON:"mdi:timelapse"},
            TP.VIDEO: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                       hass.HASS_CONFIG_ICON:"mdi:file-video"},
            TP.VIDSPEED: {
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SPEED,
                        hass.HASS_CONFIG_MIN : 2,
                        hass.HASS_CONFIG_MAX : 20,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.VIDSPEED]},
            TP.HTTP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                      hass.HASS_CONFIG_ICON:"mdi:video"},
            TP.RTSP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                      hass.HASS_CONFIG_ICON:"mdi:video"},
            TP.UDP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                     hass.HASS_CONFIG_ICON:"mdi:video"},
            TP.MOTION_EN: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                           hass.HASS_CONFIG_ICON:"mdi:video"},
            TP.MOTION: {hass.HASS_CONFIG_ICON:"mdi:motion-sensor",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_MOTION},
                        #hass.HASS_CONFIG_ATTR : f"{self.baseTopic}/{TP.MOTION}"},
            TP.SNAPTI: {hass.HASS_CONFIG_ICON:"mdi:av-timer",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DURATION,
                        hass.HASS_CONFIG_UNIT : "s",
                        hass.HASS_CONFIG_MIN : TIMER_MIN,
                        hass.HASS_CONFIG_MAX : 120,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "box",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.SNAPTI]},
            TP.VIDEOTI:{hass.HASS_CONFIG_ICON:"mdi:av-timer",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DURATION,
                        hass.HASS_CONFIG_UNIT : "s",
                        hass.HASS_CONFIG_MIN : TIMER_MIN-1, #0 = infinite
                        hass.HASS_CONFIG_MAX : 7200,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "box",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.VIDEOTI]},
            TP.SNAPCNT:{hass.HASS_CONFIG_ICON:"mdi:counter",
                       hass.HASS_CONFIG_MIN : CNT_MIN,
                       hass.HASS_CONFIG_MAX : 200,
                       hass.HASS_CONFIG_STEP : 1,
                       hass.HASS_CONFIG_MODE : "box",
                       hass.HASS_CONFIG_CMD_TP: subTopics[TP.SNAPCNT]},

            TP.TUNECTRLS : {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                           hass.HASS_CONFIG_ICON:"mdi:tune"},

            TP.TUNE_AWBEN : {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                           hass.HASS_CONFIG_ICON:"mdi:white-balance-auto"},
            TP.TUNE_AWBMODE : {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SELECT,
                              hass.HASS_CONFIG_OPTIONS : ["Auto","Tungsten","Fluorescent","Indoor","Daylight","Cloudy"],
                              hass.HASS_CONFIG_ICON:"mdi:white-balance-auto",
                              hass.HASS_CONFIG_CMD_TP: subTopics[TP.TUNE_AWBMODE]},

            TP.TUNE_BRIGHT : {hass.HASS_CONFIG_ICON:"mdi:brightness-6",
                        hass.HASS_CONFIG_MIN : -1,
                        hass.HASS_CONFIG_MAX : 1,
                        hass.HASS_CONFIG_STEP : 0.1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.TUNE_BRIGHT]},

            TP.TUNE_CONTRAST : {hass.HASS_CONFIG_ICON:"mdi:contrast-box",
                        hass.HASS_CONFIG_MIN : 0,
                        hass.HASS_CONFIG_MAX : 32,
                        hass.HASS_CONFIG_STEP : 0.1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.TUNE_CONTRAST]},

            TP.TUNE_SAT : {hass.HASS_CONFIG_ICON:"mdi:invert-colors",
                        hass.HASS_CONFIG_MIN : 0,
                        hass.HASS_CONFIG_MAX : 32,
                        hass.HASS_CONFIG_STEP : 0.1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.TUNE_SAT]},
            TP.TUNE_SHARP : {hass.HASS_CONFIG_ICON:"mdi:image-filter-black-white",
                        hass.HASS_CONFIG_MIN : 0,
                        hass.HASS_CONFIG_MAX : 16,
                        hass.HASS_CONFIG_STEP : 0.1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: subTopics[TP.TUNE_SHARP]}
            }

        for tp in self.getClientTopics(): # depends on configured HW
            match tp:
                case TP.PAN:
                    hassconfigs.update({TP.PAN:
                                        {hass.HASS_CONFIG_ICON:"mdi:pan-horizontal",
                                         hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DISTANCE,
                                         hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                         hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                                         hass.HASS_CONFIG_UNIT : "°",
                                         hass.HASS_CONFIG_MIN : self.cfg.PanTilt.Pan.angle_min,
                                         hass.HASS_CONFIG_MAX : self.cfg.PanTilt.Pan.angle_max,
                                         hass.HASS_CONFIG_STEP : 1,
                                         hass.HASS_CONFIG_MODE : "slider",
                                         hass.HASS_CONFIG_CMD_TP: subTopics[TP.PAN]}
                                        })
                case TP.TILT:
                    hassconfigs.update({TP.TILT:
                                        {hass.HASS_CONFIG_ICON:"mdi:pan-vertical",
                                         hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DISTANCE,
                                         hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                         hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                                         hass.HASS_CONFIG_UNIT : "°",
                                         hass.HASS_CONFIG_MIN : self.cfg.PanTilt.Tilt.angle_low,
                                         hass.HASS_CONFIG_MAX : self.cfg.PanTilt.Tilt.angle_high,
                                         hass.HASS_CONFIG_STEP : 1,
                                         hass.HASS_CONFIG_MODE : "slider",
                                         hass.HASS_CONFIG_CMD_TP: subTopics[TP.TILT]}
                                        })
                case TP.PANA:
                    hassconfigs.update({TP.PANA:
                                        {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                                         hass.HASS_CONFIG_ICON:"mdi:pan-horizontal"}
                                         })
                case TP.LSENS:
                    hassconfigs.update({TP.LSENS:
                                        {hass.HASS_CONFIG_ICON:"mdi:brightness-5",
                                         hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_ILLUMINANCE,
                                         hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                         hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}"}
                                         })
                case "_":
                    pass

        return hassconfigs
