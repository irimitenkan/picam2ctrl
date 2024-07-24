'''
Created on 28.03.2022

@author: irimi
'''

import re
import logging
import signal

import MQTTClient as hass

from time import sleep
from utils import ThreadEvents
from config import Config,CheckConfig
from threading import Semaphore
from picam2 import ImageCapture, VideoCapture,VideoCaptureElapse, HTTPStreamCapture
from picam2 import getCameraInfo, UDPStreamCapture
from pantilt.ULN2003.stepmotors import PanTiltStepMotors
from pantilt.waveshare.servomotors import PanTiltServoMotors
from pantilt.waveshare.lightsensor import LightSensor

MQTT_CLIENT_ID = 'picam2ctrl'
TIMER_MIN = 1
RATE_MIN = 1
RATE_MAX = 50
CNT_MIN = 0
"""
QOS: 0 => fire and forget A -> B
QOS: 1 => at leat one - msg will be send
          (A) since publish_ack (B) is not received
QOS: 3 => exactly once :
          Publish (A) -> PubRec (B) -> PUBREL (A) -> PUBCOM (B) -> A
"""
QOS = 0

""" True: MSG is stored at Broker and keeps available for new subscribes,
    False: new publish required after subscribes
"""
RETAIN = True

""" Logging level: INFO, DEBUG, ERROR, WARN  """
LOG_LEVEL = {
    "INFO": logging.INFO,
    "ERROR": logging.ERROR,
    "WARN": logging.WARN,
    "DEBUG": logging.DEBUG
}
TP_REC = "Recording"
TP_SNAP = "Snapshot"
TP_SNAPCNT = "SnapCounter"
TP_SNAPTI = "SnapTimer"
TP_VIDEO = "Video"
TP_VIDEOTI = "VideoTimer"
TP_VIDSPEED = "VidLapseSpeed"
TP_HTTP = "HttpStream"
TP_TIMELAPSE = "TimeLapse"
TP_UDP = "UdpStream"
TP_MOTION = "Motion"
TP_MOTION_EN = "MotionEnabled"
TP_PAN = "Pan"
TP_TILT = "Tilt"
TP_PANA = "PanAutomation"
TP_LSENS = "Lightsensor"

class PiCam2Client (hass.MQTTClient):
    """ MQTT client class """

    def __init__(self, cfg):
        self._disconnectRQ = False
        self.cfg = cfg
        self._mqtt_client = None
        self._update = False
        self._online = False
        self._video = False
        self._snapshot = False
        self._hstream = False
        self._ustream = False
        self._motionEnabled = cfg.startup.motion
        self._child = None
        self._panAngle = self.cfg.startup.PanAngle
        self._tiltAngle = self.cfg.startup.TiltAngle
        self.pan_semaphore = Semaphore()
        self.tilt_semaphore = Semaphore()
        self.manufacturer = "unknown"
        self.swversion = "x.x"
        self.activeThreads=ThreadEvents()
        self._lightSensor= None
        super().__init__(cfg, MQTT_CLIENT_ID)

        signal.signal(signal.SIGINT, self.daemon_kill)
        signal.signal(signal.SIGTERM, self.daemon_kill)

        self.autoStart()

    def clientLoop (self):
        """
        overload default clientLoop behaviour
        """
        pass

    def autoStart(self):
        """
        autostart function for clientstart.
        only one single camera task is allowed
        """
        if self.cfg.startup.snap:
            self._enableSnapShot()
        elif self.cfg.startup.video:
            self._enableVideo(False)
        elif self.cfg.startup.videolapse:
            self._enableVideo(True)
        elif self.cfg.startup.httpStream:
            self._enableHttpStream()
        elif self.cfg.startup.udpStream:
            self._enableUdpStream()

    def setupClientTopics(self)->dict:
        """
        get a dict() which defines the required client topic
        based on HASS types
        """

        clientTopics = {TP_REC: hass.HASS_COMPONENT_BINARY_SENSOR,
                        TP_SNAP: hass.HASS_COMPONENT_SWITCH,
                        TP_SNAPTI: hass.HASS_COMPONENT_NUMBER,
                        TP_SNAPCNT: hass.HASS_COMPONENT_NUMBER,
                        TP_VIDEO: hass.HASS_COMPONENT_SWITCH,
                        TP_VIDEOTI: hass.HASS_COMPONENT_NUMBER,
                        TP_VIDSPEED: hass.HASS_COMPONENT_NUMBER,
                        TP_TIMELAPSE: hass.HASS_COMPONENT_SWITCH,
                        TP_HTTP: hass.HASS_COMPONENT_SWITCH,
                        TP_UDP: hass.HASS_COMPONENT_SWITCH,
                        TP_MOTION_EN: hass.HASS_COMPONENT_SWITCH,
                        TP_MOTION: hass.HASS_COMPONENT_BINARY_SENSOR,
                        TP_PANA: hass.HASS_COMPONENT_SWITCH,
                        TP_PAN: hass.HASS_COMPONENT_NUMBER,
                        TP_TILT: hass.HASS_COMPONENT_NUMBER,
                        TP_LSENS: hass.HASS_COMPONENT_SENSOR}

        return self.removeTpsByHW(clientTopics)

    def removeTpsByHW(self,tps:dict) -> dict:
        """
        remove topics again if HW not available and not defined in json.cfg
        """
        if not CheckConfig.HasTilt(self.cfg):
            del tps[TP_TILT]
        if not CheckConfig.HasPanTilt(self.cfg):
            del tps[TP_PAN]
            del tps[TP_PANA]
        if not CheckConfig.HasLightSens(self.cfg):
            del tps[TP_LSENS]

        return tps

    def setupHassDiscoveryConfigs(self) -> dict:
        """
        get a dict() which defines the required config topics
        based on HASS
        """
        hassconfigs = {
            TP_REC: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_RUNNING,
                     hass.HASS_CONFIG_PAYLOAD_ON : True,
                     hass.HASS_CONFIG_PAYLOAD_OFF : False},
            TP_SNAP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                      hass.HASS_CONFIG_ICON:"mdi:camera"},
            TP_TIMELAPSE:{hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                          hass.HASS_CONFIG_ICON:"mdi:timelapse"},
            TP_VIDEO: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                       hass.HASS_CONFIG_ICON:"mdi:file-video"},
            TP_VIDSPEED: {
                        #hass.HASS_CONFIG_ICON:"mdi:speedometer",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SPEED,
                        #hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                        #hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                        hass.HASS_CONFIG_MIN : 2,
                        hass.HASS_CONFIG_MAX : 20,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "slider",
                        hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_VIDSPEED]},
            TP_HTTP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                      hass.HASS_CONFIG_ICON:"mdi:video"},
            TP_UDP: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                     hass.HASS_CONFIG_ICON:"mdi:video"},
            TP_MOTION_EN: {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                           hass.HASS_CONFIG_ICON:"mdi:video"},
            TP_MOTION: {hass.HASS_CONFIG_ICON:"mdi:motion-sensor",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_MOTION},
                        #hass.HASS_CONFIG_ATTR : f"{self.baseTopic}/{TP_MOTION}"},
            TP_SNAPTI: {hass.HASS_CONFIG_ICON:"mdi:av-timer",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DURATION,
                        #hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                        #hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                        hass.HASS_CONFIG_UNIT : "s",
                        hass.HASS_CONFIG_MIN : TIMER_MIN,
                        hass.HASS_CONFIG_MAX : 120,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "box",
                        hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_SNAPTI]},
            TP_VIDEOTI:{hass.HASS_CONFIG_ICON:"mdi:av-timer",
                        hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DURATION,
                        #hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                        #hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                        hass.HASS_CONFIG_UNIT : "s",
                        hass.HASS_CONFIG_MIN : TIMER_MIN,
                        hass.HASS_CONFIG_MAX : 7200,
                        hass.HASS_CONFIG_STEP : 1,
                        hass.HASS_CONFIG_MODE : "box",
                        hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_VIDEOTI]},
            TP_SNAPCNT:{hass.HASS_CONFIG_ICON:"mdi:counter",
                       #HASS device class counter unknown
                       hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_NONE,
                       #hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                       #hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                       hass.HASS_CONFIG_MIN : CNT_MIN,
                       hass.HASS_CONFIG_MAX : 200,
                       hass.HASS_CONFIG_STEP : 1,
                       hass.HASS_CONFIG_MODE : "box",
                       hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_SNAPCNT]}
            }
        for tp in self.setupClientTopics(): # depends on configured HW
            if TP_PAN == tp:
                hassconfigs.update({TP_PAN:
                                    {hass.HASS_CONFIG_ICON:"mdi:pan-horizontal",
                                     hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DISTANCE,
                                     hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                     hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                                     hass.HASS_CONFIG_UNIT : "°",
                                     hass.HASS_CONFIG_MIN : self.cfg.PanTilt.Pan.angle_min,
                                     hass.HASS_CONFIG_MAX : self.cfg.PanTilt.Pan.angle_max,
                                     hass.HASS_CONFIG_STEP : 1,
                                     hass.HASS_CONFIG_MODE : "slider",
                                     hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_PAN]}
                                    })
            elif TP_TILT == tp:
                hassconfigs.update({TP_TILT:
                                    {hass.HASS_CONFIG_ICON:"mdi:pan-vertical",
                                     hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_DISTANCE,
                                     hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                     hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}",
                                     hass.HASS_CONFIG_UNIT : "°",
                                     hass.HASS_CONFIG_MIN : self.cfg.PanTilt.Tilt.angle_low,
                                     hass.HASS_CONFIG_MAX : self.cfg.PanTilt.Tilt.angle_high,
                                     hass.HASS_CONFIG_STEP : 1,
                                     hass.HASS_CONFIG_MODE : "slider",
                                     hass.HASS_CONFIG_CMD_TP: self._subTopics[TP_TILT]}
                                    })
            elif TP_PANA == tp:
                hassconfigs.update({TP_PANA:
                                    {hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_SWITCH,
                                     hass.HASS_CONFIG_ICON:"mdi:pan-horizontal"}
                                     })
            elif TP_LSENS == tp:
                hassconfigs.update({TP_LSENS:
                                    {hass.HASS_CONFIG_ICON:"mdi:brightness-5",
                                     hass.HASS_CONFIG_DEVICE_CLASS : hass.HASS_CLASS_ILLUMINANCE,
                                     hass.HASS_CONFIG_VALUE_TEMPLATE :"{{ value }}",
                                     hass.HASS_CONFIG_CMD_TEMPLATE :"{{ value }}"}
                                     })
        
        return hassconfigs

    def setupDevice(self):
        """
        setup device(s) used for client communication
        """
        info = getCameraInfo()
        logging.debug(str(info))
        if self.cfg.camera.index + 1 > len(info[0]):
            logging.error(
                f"camera index - but only {len(info[0])} camera(s) detected")
        else:
            self.model = info[0][self.cfg.camera.index].get("Model", "tbd")
            logging.info(
                f"configured camera model:{self.model} ,detected: {len(info[0])}")
            fnd = re.search("([vV][0-9][\S]+)", info[1])
            if fnd:
                self.swversion = fnd.group()
                logging.debug("SWVersion = " + self.swversion)

        if self.model.startswith("imx") or self.model.startswith("ov"):
            self.manufacturer = "Raspberry Pi"

        if CheckConfig.HasULN2003(self.cfg):
            self._PanTiltCam = PanTiltStepMotors(self, self.cfg)
        elif CheckConfig.HasWaveShare(self.cfg):
            self._PanTiltCam = PanTiltServoMotors(self, self.cfg)
            if CheckConfig.HasLightSens(self.cfg):
                self._lightSensor=LightSensor(self,self.cfg.PanTilt.WAVESHARE_HAT.sensorRefresh)
        else:
            logging.debug("No PanTilt HW configured")
            self._PanTiltCam = None

        if self._PanTiltCam:
            self.activeThreads.addThread(self._PanTiltCam)

        for tp in self.TopicValues:
            val = self.TopicValues[tp]
            if TP_REC == tp:
                val= False
            elif TP_SNAP == tp:
                val= hass.HASS_STATE_ON if self.cfg.startup.snap else hass.HASS_STATE_OFF
            elif TP_VIDEO == tp:
                val= hass.HASS_STATE_ON if self.cfg.startup.video else hass.HASS_STATE_OFF
            elif TP_TIMELAPSE == tp:
                val= hass.HASS_STATE_OFF
            elif TP_VIDSPEED == tp:
                val= self.cfg.startup.VideoLapseSpeed
            elif TP_HTTP == tp:
                val= hass.HASS_STATE_ON if self.cfg.startup.httpStream else hass.HASS_STATE_OFF
            elif TP_UDP == tp:
                val= hass.HASS_STATE_ON if self.cfg.startup.udpStream else hass.HASS_STATE_OFF
            elif TP_MOTION_EN == tp:
                val= hass.HASS_STATE_ON if self.cfg.startup.motion else hass.HASS_STATE_OFF
            elif TP_MOTION == tp:
                val = False
            elif TP_PANA == tp and self._PanTiltCam:
                if self.cfg.startup.panAuto:
                    self._PanTiltCam.pan_rotate_auto(True)
                    val= hass.HASS_STATE_ON# if self._PanTiltCam.get_Pana_active() else hass.HASS_STATE_OFF
            elif TP_PAN == tp:
                val = self._panAngle
            elif TP_TILT == tp:
                val = self._tiltAngle
            elif TP_SNAPTI == tp:
                val = self.cfg.startup.SnapTimer
            elif TP_VIDEOTI == tp:
                val = self.cfg.startup.VideoTimer
            elif TP_TILT == tp:
                val = self._tiltAngle
            elif TP_SNAPCNT == tp:
                val = self.cfg.startup.SnapCount #0 = endöess

            self.TopicValues[tp]= val

        mqtt_device = {
            "identifiers": [f"{MQTT_CLIENT_ID}_{self._hostname}"],
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sw_version": self.swversion,
            "name": f"{MQTT_CLIENT_ID}.{self._hostname}.PiCamera2"
        }
        return mqtt_device

    def _enableSnapShot(self):
        """
        enable Snapshot task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable Snapshot Task")
            self._child = ImageCapture(self, self.cfg,
                                       self.TopicValues[TP_SNAPTI],
                                       self.TopicValues[TP_SNAPCNT],
                                       self.TopicValues[TP_TIMELAPSE]==hass.HASS_STATE_ON,
                                       self._motionEnabled)
            self._snapshot = True
            self.activeThreads.addThread(self._child)
            self.publish_state(TP_SNAP)
            self.TopicValues[TP_REC]=True
            self.publish_state(TP_REC)

    def _enableVideo(self,bTimeLapse):
        """
        enable video task: this called by on_message or after startup
        """
        if not self._child:
            if bTimeLapse:
                logging.debug("enable VideoLapse Task")
                self._child = VideoCaptureElapse(self, self.cfg,
                                           self.TopicValues[TP_VIDEOTI],
                                           self.TopicValues[TP_VIDSPEED],
                                           self._motionEnabled)
            else:
                logging.debug("enable Video Task")
                self._child = VideoCapture(self, self.cfg,
                                           self.TopicValues[TP_VIDEOTI],
                                           self._motionEnabled)
            self._video = True
            self.publish_state(TP_VIDEO)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP_REC]=True
            self.publish_state(TP_REC)

    def _enableHttpStream(self):
        """
        enable http streaming task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable HttpStream Task")
            self._child = HTTPStreamCapture(self, self.cfg, self._motionEnabled)
            self._hstream = True
            self.publish_state(TP_HTTP)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP_REC]=True
            self.publish_state(TP_REC)

    def _enableUdpStream(self):
        """
        enable udp streaming task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable UdpStream Task")
            self._child = UDPStreamCapture(self, self.cfg, self._motionEnabled)
            self._ustream = True
            self.publish_state(TP_UDP)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP_REC]=True
            self.publish_state(TP_REC)

    def gettiltAngle(self,angle:int) -> int:
        fl=1
        if self.cfg.PanTilt.Tilt.flip:
            fl=-1
        return angle*fl

    def getpanAngle(self,angle) -> int:
        fl=1
        if self.cfg.PanTilt.Pan.flip:
            fl=-1
        return angle*fl

    def publish_avail_topics(self,avail=True):

        if self._lightSensor:
            if avail:
                self.activeThreads.addThread(self._lightSensor)
        else:
            pass

        super().publish_avail_topics(avail)

    def on_message(self, _client, _userdata, message):
        """
        on_message event by broker
        """
        payload = hass.toStr(message.payload)
        logging.debug(f"on message topic {message.topic}:{payload}")

        for tp in self._subTopics:
            logging.debug(f"check on_message for: {self._subTopics[tp]}")
            if self._subTopics[tp]==message.topic:
                if TP_PAN == tp:
                    logging.debug(f"Camera PAN request {payload}")
                    self._panAngle = self.getpanAngle(int(payload))
                    if self._PanTiltCam and not self._PanTiltCam.get_Pana_active():
                        self.pan_semaphore.acquire()
                        self._PanTiltCam.pan_rotate_to(self._panAngle)
                        self.pan_semaphore.release()
                    break
                elif TP_TILT == tp:
                    logging.debug(f"Camera TILT request {payload}")
                    self._tiltAngle=self.gettiltAngle(int(payload))
                    if self._PanTiltCam:
                        self.tilt_semaphore.acquire()
                        self._PanTiltCam.tilt_rotate_to(self._tiltAngle)
                        self.tilt_semaphore.release()
                    break
                elif TP_PANA == tp:
                    logging.debug(f"Camera PAN Auto Motion {payload}")
                    if self._PanTiltCam:
                        self.TopicValues[tp]= payload
                        if payload == hass.HASS_STATE_ON and not self._PanTiltCam.get_Pana_active():
                            active=True
                        elif payload == hass.HASS_STATE_OFF and self._PanTiltCam.get_Pana_active():
                            active=False
                        self._PanTiltCam.pan_rotate_auto(active)
                        self.publish_state(self._stTopics[tp], payload= payload)
                    break
                elif TP_MOTION_EN == tp:
                    self.TopicValues[tp]= payload
                    if payload == hass.HASS_STATE_ON and not self._child:
                        #ignore since child app is active
                        self._motionEnabled = True
                        self.publish_state(TP_MOTION_EN)
                        self.publish_avail(self._avTopics[TP_MOTION])
                    elif payload == hass.HASS_STATE_OFF:
                        self._motionEnabled = False
                        self.publish_state(TP_MOTION_EN)
                        self.publish_avail(self._avTopics[TP_MOTION], False)
                        if self._child:  # # already active -> disable
                            self._child.trigger_stop()
                    break
                elif not self._child:
                    if TP_SNAP == tp:
                        self.TopicValues[tp]= payload
                        if payload == hass.HASS_STATE_ON:
                            self._enableSnapShot()
                        break
                    elif TP_SNAPTI == tp:
                        self.TopicValues[tp]= payload
                        self.publish_state(TP_SNAPTI)
                        break
                    elif TP_SNAPCNT == tp:
                        self.TopicValues[tp]= payload
                        self.publish_state(TP_SNAPCNT)
                        break
                    elif TP_VIDEOTI == tp:
                        self.TopicValues[tp]= payload
                        self.publish_state(TP_VIDEOTI)
                        break
                    elif TP_TIMELAPSE == tp:
                        self.TopicValues[tp]= payload
                        self.publish_state(TP_TIMELAPSE)
                        break
                    elif TP_VIDSPEED == tp:
                        self.TopicValues[tp]= payload
                        self.publish_state(TP_VIDSPEED)
                        break
                    elif TP_VIDEO == tp:
                        self.TopicValues[tp]= payload
                        if payload == hass.HASS_STATE_ON:
                            self._enableVideo(hass.HASS_STATE_ON==self.TopicValues[TP_TIMELAPSE])
                        break
                    elif TP_HTTP == tp:
                        self.TopicValues[tp]= payload
                        if payload == hass.HASS_STATE_ON:
                            self._enableHttpStream()
                        break
                    elif TP_UDP == tp:
                        self.TopicValues[tp]= payload
                        if payload == hass.HASS_STATE_ON:
                            self._enableUdpStream()
                        break
                    else:
                        logging.warning("unhandled payload" + payload)
                        break
                else:
                    if TP_SNAP == tp and \
                            isinstance(self._child, ImageCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP_VIDEO == tp and \
                            isinstance(self._child, VideoCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP_HTTP == tp and \
                            isinstance(self._child, HTTPStreamCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP_UDP == tp and \
                            isinstance(self._child, UDPStreamCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    else:
                        logging.warning(f"Ignoring request {message.topic}:{payload}")
                        break

    def client_down(self):
        """
        clean up everything when keyboard CTRL-C or daemon kill request occurs
        """
        super().client_down()
        self.activeThreads.stopAllThreads()

    def child_down(self, child):
        """ callback function when picam2 threads stop """
        logging.debug("child_down received:" + str(child))
        self.activeThreads.rmThread(child)

        if isinstance(child, ImageCapture):
            self._snapshot = False
            self.TopicValues[TP_SNAP] = hass.HASS_STATE_OFF
            self.publish_state(TP_SNAP)
            self.TopicValues[TP_REC]=False
            self.publish_state(TP_REC)
            self._child = None
        elif isinstance(child, VideoCapture) or \
             isinstance(child, VideoCaptureElapse) :
            self._video = False
            self.TopicValues[TP_VIDEO] = hass.HASS_STATE_OFF
            self.publish_state(TP_VIDEO)
            self.TopicValues[TP_REC]=False
            self.publish_state(TP_REC)
            self._child = None
        elif isinstance(child, HTTPStreamCapture):
            self._hstream = False
            self.TopicValues[TP_HTTP] = hass.HASS_STATE_OFF
            self.publish_state(TP_HTTP)
            self.TopicValues[TP_REC]=False
            self.publish_state(TP_REC)
            self._child = None
        elif isinstance(child, UDPStreamCapture):
            self._ustream = False
            self.TopicValues[TP_UDP] = hass.HASS_STATE_OFF
            self.publish_state(TP_UDP)
            self._child = None
            self.TopicValues[TP_REC]=False
            self.publish_state(TP_REC)
        elif isinstance(child, PanTiltServoMotors) or \
             isinstance(child, PanTiltStepMotors) :
            self._PanTiltCam=None # delete old reference
        else:
            logging.warning("unhandled client down instance")

    def motion_detected(self):
        """ callback function when motion has been detected """
        logging.debug("callback motion_detected")
        self.publish_state(self._stTopics[TP_MOTION],
                            hass.encode_json({"occupancy": True}))
        sleep(0.5)
        self.publish_state(self._stTopics[TP_MOTION],
                            hass.encode_json({"occupancy": False}))

    def pan_update(self,angle:int):
        """ callback function to PanTiltCam pan angle """
        logging.debug(f"callback pan_update:{angle}°")
        self._panAngle = self.getpanAngle(angle)
        self.TopicValues[TP_PAN] = self._panAngle
        self.publish_state(TP_PAN)

    def tilt_update(self,angle:int):
        """ callback function for updating PanTiltCam tilt angle """
        logging.debug(f"callback tilt_update:{angle}°")
        self._tiltAngle = self.gettiltAngle(angle)
        self.TopicValues[TP_TILT] = self._tiltAngle
        self.publish_state(TP_TILT)

    def light_update(self,lux:int):
        """ callback function when light sensor update available """
        logging.debug(f"callback lux_update:{lux}")
        self.publish_state(self._stTopics[TP_LSENS],
                                hass.encode_json({"illuminance": lux}))

def startClient(cfgfile: str):
    """
    generator help function to create MQTT client instance  & start it
    """

    cfg=Config.load_json(cfgfile)
    logging.basicConfig(level=LOG_LEVEL[cfg.LogLevel],
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%H:%M:%S')
    #validate config only
    if CheckConfig.HasValidStartup(cfg):
        CheckConfig.HasPanTilt(cfg)
        client = PiCam2Client(cfg)
        client.startup_client()
