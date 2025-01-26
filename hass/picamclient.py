'''
Created on 28.03.2022

@author: irimi
'''

import re
import logging
import signal

from hass import MQTTClient as hass

from time import sleep
from utils import ThreadEvents
from config import Config,CheckConfig
from threading import Semaphore
from picam2 import ImageCapture, VideoCapture,VideoCaptureElapse, HTTPStreamCapture
from picam2 import getCameraInfo, UDPStreamCapture
from pantilt.ULN2003.stepmotors import PanTiltStepMotors
from pantilt.waveshare.servomotors import PanTiltServoMotors
from pantilt.waveshare.lightsensor import LightSensor
from hass.picamTopics import TP

MQTT_CLIENT_ID = 'picam2ctrl'
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
        self.tps=TP(cfg)
        self.actCtrls=dict() # empty
        super().__init__(cfg, MQTT_CLIENT_ID,cfg.HASS_Node_ID)

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
        if self.cfg.camera.CtrlsEnabled:
            self.actCtrls=self.tps.TuneCtrls.copy()

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
        return self.tps.getClientTopics()

    def setupHassDiscoveryConfigs(self) -> dict:
        """
        get a dict() which defines the required config topics
        based on HASS
        """
        return self.tps.getHassConfigs(self._subTopics)

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

        mqtt_device = {
            "identifiers": [f"{self._hostTpId}"],
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sw_version": self.swversion,
            "name": f"{self._hostTpId}"
        }
        return mqtt_device

    def _enableSnapShot(self):
        """
        enable Snapshot task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable Snapshot Task")
            self._child = ImageCapture(self, self.cfg,
                                       self.actCtrls,
                                       self._motionEnabled,
                                       self.TopicValues[TP.SNAPTI],
                                       self.TopicValues[TP.SNAPCNT],
                                       self.TopicValues[TP.TIMELAPSE]==hass.HASS_STATE_ON
                                       )
            self._snapshot = True
            self.activeThreads.addThread(self._child)
            self.publish_state(TP.SNAP)
            self.TopicValues[TP.REC]=True
            self.publish_state(TP.REC)

    def _enableVideo(self,bTimeLapse):
        """
        enable video task: this called by on_message or after startup
        """
        if not self._child:
            if bTimeLapse:
                logging.debug("enable VideoLapse Task")
                self._child = VideoCaptureElapse(self, self.cfg,
                                                self.actCtrls,
                                                self._motionEnabled,
                                                self.TopicValues[TP.VIDEOTI],
                                                self.TopicValues[TP.VIDSPEED])
            else:
                logging.debug("enable Video Task")
                self._child = VideoCapture(self, self.cfg,
                                           self.actCtrls,
                                           self._motionEnabled,
                                           self.TopicValues[TP.VIDEOTI])
            self._video = True
            self.publish_state(TP.VIDEO)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP.REC]=True
            self.publish_state(TP.REC)

    def _enableHttpStream(self):
        """
        enable http streaming task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable HttpStream Task")
            self._child = HTTPStreamCapture(self, self.cfg, self.actCtrls, self._motionEnabled)
            self._hstream = True
            self.publish_state(TP.HTTP)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP.REC]=True
            self.publish_state(TP.REC)

    def _enableUdpStream(self):
        """
        enable udp streaming task: this called by on_message or after startup
        """
        if not self._child:
            logging.debug("enable UdpStream Task")
            self._child = UDPStreamCapture(self, self.cfg, self.actCtrls, self._motionEnabled)
            self._ustream = True
            self.publish_state(TP.UDP)
            self.activeThreads.addThread(self._child)
            self.TopicValues[TP.REC]=True
            self.publish_state(TP.REC)

    def setupInitValues(self):
        """
        setup all init values in dict self.TopicValues
        """
        self.tps.setInitValues(self.TopicValues)

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
        na =self.tps.getInitNonAvail()
        for t in self._avTopics:
            logging.debug(f"checking  {t}")
            if t in na:
                self.publish_avail(self._avTopics[t], False)
            else:
                self.publish_avail(self._avTopics[t], avail)

    def on_message(self, _client, _userdata, message):
        """
        on_message event by broker
        """
        super().on_message(_client, _userdata, message)
        payload = hass.toStr(message.payload)
        logging.debug(f"on message topic {message.topic}:{payload}")

        for tp in self._subTopics:
            logging.debug(f"check on_message for: {self._subTopics[tp]}")
            if self._subTopics[tp]==message.topic:
                if TP.PAN == tp:
                    logging.debug(f"Camera PAN request {payload}")
                    self._panAngle = self.getpanAngle(int(payload))
                    if self._PanTiltCam and not self._PanTiltCam.get_Pana_active():
                        self.pan_semaphore.acquire()
                        self._PanTiltCam.pan_rotate_to(self._panAngle)
                        self.pan_semaphore.release()
                    break
                elif TP.TILT == tp:
                    logging.debug(f"Camera TILT request {payload}")
                    self._tiltAngle=self.gettiltAngle(int(payload))
                    if self._PanTiltCam:
                        self.tilt_semaphore.acquire()
                        self._PanTiltCam.tilt_rotate_to(self._tiltAngle)
                        self.tilt_semaphore.release()
                    break
                elif TP.PANA == tp:
                    logging.debug(f"Camera PAN Auto Motion {payload}")
                    if self._PanTiltCam:
                        if payload == hass.HASS_STATE_ON and not self._PanTiltCam.get_Pana_active():
                            active=True
                        elif payload == hass.HASS_STATE_OFF and self._PanTiltCam.get_Pana_active():
                            active=False
                        self._PanTiltCam.pan_rotate_auto(active)
                        self.publish_state(self._stTopics[tp], payload= payload)
                    break
                elif TP.MOTION_EN == tp:
                    if payload == hass.HASS_STATE_ON and not self._child:
                        #ignore since child app is active
                        self._motionEnabled = True
                        self.publish_state(TP.MOTION_EN)
                        self.publish_avail(self._avTopics[TP.MOTION])
                    elif payload == hass.HASS_STATE_OFF:
                        self._motionEnabled = False
                        self.publish_state(TP.MOTION_EN)
                        self.publish_avail(self._avTopics[TP.MOTION], False)
                        if self._child:  # # already active -> disable
                            self._child.trigger_stop()
                    break
                elif TP.TUNECTRLS == tp:
                    self.publish_state(TP.TUNECTRLS)
                    if payload == hass.HASS_STATE_ON:
                        self.actCtrls=self.tps.TuneCtrls.copy()
                        if self._child:
                            self._child.updateCtrls(self.actCtrls)
                    elif payload == hass.HASS_STATE_OFF:
                        self.actCtrls = dict()
                        if self._child:
                            self._child.updateCtrls(self.actCtrls)
                    break

                elif tp in self.tps.TuneCtrls:
                    self.publish_state(tp)
                    if tp in self.tps.TuneCtrlsDigits:
                        self.tps.TuneCtrls[tp]=float(payload)
                    else:
                        self.tps.TuneCtrls[tp]=payload
                    logging.debug(f"self.tps.TuneCtrls = {self.tps.TuneCtrls}")
                    if hass.HASS_STATE_ON == self.TopicValues[TP.TUNECTRLS]:
                        self.actCtrls=self.tps.TuneCtrls.copy()
                        if self._child:
                            self._child.updateCtrls(self.actCtrls)
                    break

                elif not self._child:
                    if TP.SNAP == tp:
                        if payload == hass.HASS_STATE_ON:
                            self._enableSnapShot()
                        break
                    elif TP.SNAPTI == tp:
                        self.publish_state(TP.SNAPTI)
                        break
                    elif TP.SNAPCNT == tp:
                        self.publish_state(TP.SNAPCNT)
                        break
                    elif TP.VIDEOTI == tp:
                        self.publish_state(TP.VIDEOTI)
                        break
                    elif TP.TIMELAPSE == tp:
                        self.publish_state(TP.TIMELAPSE)
                        break
                    elif TP.VIDSPEED == tp:
                        self.publish_state(TP.VIDSPEED)
                        break
                    elif TP.VIDEO == tp:
                        if payload == hass.HASS_STATE_ON:
                            self._enableVideo( hass.HASS_STATE_ON==self.TopicValues[TP.TIMELAPSE])
                        break
                    elif TP.HTTP == tp:
                        if payload == hass.HASS_STATE_ON:
                            self._enableHttpStream()
                        break
                    elif TP.UDP == tp:
                        if payload == hass.HASS_STATE_ON:
                            self._enableUdpStream()
                        break
                    else:
                        logging.warning("unhandled payload:" + payload)
                        break
                else:
                    if TP.SNAP == tp and \
                            isinstance(self._child, ImageCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP.VIDEO == tp and \
                            isinstance(self._child, VideoCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP.HTTP == tp and \
                            isinstance(self._child, HTTPStreamCapture):
                        if payload == hass.HASS_STATE_OFF:
                            self._child.trigger_stop()
                        break
                    elif TP.UDP == tp and \
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
            self.TopicValues[TP.SNAP] = hass.HASS_STATE_OFF
            self.publish_state(TP.SNAP)
            self.TopicValues[TP.REC]=False
            self.publish_state(TP.REC)
            self._child = None
        elif isinstance(child, VideoCapture) or \
             isinstance(child, VideoCaptureElapse) :
            self._video = False
            self.TopicValues[TP.VIDEO] = hass.HASS_STATE_OFF
            self.publish_state(TP.VIDEO)
            self.TopicValues[TP.REC]=False
            self.publish_state(TP.REC)
            self._child = None
        elif isinstance(child, HTTPStreamCapture):
            self._hstream = False
            self.TopicValues[TP.HTTP] = hass.HASS_STATE_OFF
            self.publish_state(TP.HTTP)
            self.TopicValues[TP.REC]=False
            self.publish_state(TP.REC)
            self._child = None
        elif isinstance(child, UDPStreamCapture):
            self._ustream = False
            self.TopicValues[TP.UDP] = hass.HASS_STATE_OFF
            self.publish_state(TP.UDP)
            self._child = None
            self.TopicValues[TP.REC]=False
            self.publish_state(TP.REC)
        elif isinstance(child, PanTiltServoMotors) or \
             isinstance(child, PanTiltStepMotors) :
            self._PanTiltCam=None # delete old reference
        else:
            logging.warning("unhandled client down instance")

    def motion_detected(self):
        """ callback function when motion has been detected """
        logging.debug("callback motion_detected")
        self.publish_state(self._stTopics[TP.MOTION],
                            hass.encode_json({"occupancy": True}))
        sleep(0.5)
        self.publish_state(self._stTopics[TP.MOTION],
                            hass.encode_json({"occupancy": False}))

    def pan_update(self,angle:int):
        """ callback function to PanTiltCam pan angle """
        logging.debug(f"callback pan_update:{angle}°")
        self._panAngle = self.getpanAngle(angle)
        self.TopicValues[TP.PAN] = self._panAngle
        self.publish_state(TP.PAN)

    def tilt_update(self,angle:int):
        """ callback function for updating PanTiltCam tilt angle """
        logging.debug(f"callback tilt_update:{angle}°")
        self._tiltAngle = self.gettiltAngle(angle)
        self.TopicValues[TP.TILT] = self._tiltAngle
        self.publish_state(TP.TILT)

    def light_update(self,lux:int):
        """ callback function when light sensor update available """
        logging.debug(f"callback lux_update:{lux}")
        self.publish_state(self._stTopics[TP.LSENS],
                                hass.encode_json({"illuminance": lux}))

def startClient(cfgfile: str):
    """
    generator help function to create MQTT client instance  & start it
    """

    cfg=Config.load_json(cfgfile)
    if cfg:
        logging.basicConfig(level=LOG_LEVEL[cfg.LogLevel],
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            datefmt='%H:%M:%S')
        #validate config only
        if CheckConfig.HasValidStartup(cfg):
            CheckConfig.HasPanTilt(cfg)
            client = PiCam2Client(cfg)
            client.startup_client()
    else:
        logging.error(f"load of {cfgfile} has failed - exit()")
        exit (-5)
