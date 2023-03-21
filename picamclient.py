'''
Created on 28.03.2022

@author: irimi
'''

import time
import re
import logging
import json
import socket
import ssl
import signal

import paho.mqtt.client as mqtt

from enum import Enum
from utils import Config
from threading import Semaphore
from paho.mqtt.client import connack_string as conn_ack
from picam2 import ImageCapture, VideoCapture, HTTPStreamCapture
from picam2 import PanCam, getCameraInfo, UDPStreamCapture

hostname = socket.gethostname()
MQTT_CLIENT_ID = 'picam2ctrl'
HASS_DISCOVERY_PREFIX = 'homeassistant'
BASE_TOPIC = f"{MQTT_CLIENT_ID}/{hostname}"

"""
QOS: 0 => fire and forget A -> B
QOS: 1 => at leat one - msg will be send
          (A) since publish_ack (B) is not received
QOS: 3 => exactly once :
          Publish (A) -> PubRec (B) -> PUBREL (A) -> PUBCOM (B) -> A
"""
QOS = 1

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

""" client topics as enumeration """
class eTPCS(Enum):
    ONLINE_STATE = 1
    
    SNAPSHOT_STATE = 10
    VIDEO_STATE = 11
    HSTREAM_STATE = 12
    USTREAM_STATE = 13
    MOTIONENABLE_STATE = 14
    PAN_STATE = 15
    PANA_STATE = 16
    END_STATE = 17
    
    SNAPSHOT_AVAIL = 20
    VIDEO_AVAIL = 21
    HSTREAM_AVAIL = 22
    USTREAM_AVAIL = 23
    MOTIONENABLE_AVAIL = 24
    PAN_AVAIL = 25
    PANA_AVAIL = 25
    END_AVAIL = 26
    
    SNAPSHOT_SET = 30
    VIDEO_SET = 31
    HSTREAM_SET = 32
    USTREAM_SET = 33
    MOTIONENABLE_SET = 34
    PAN_SET = 35
    PANA_SET = 36
    END_SET = 37
    
    # BINARY SWITCH
    MOTION_AVAIL = 45
    MOTION_STATE = 46
    
    HASS_DISCOVERY_SNAPSHOT = 50
    HASS_DISCOVERY_VIDEO = 51
    HASS_DISCOVERY_HSTREAM = 52
    HASS_DISCOVERY_USTREAM = 53
    HASS_DISCOVERY_MOTIONENABLE = 54
    HASS_DISCOVERY_MOTION = 55
    HASS_DISCOVERY_PAN = 56
    HASS_DISCOVERY_PANA = 57


""" client topics dictionary eTCPS - topic as string """
TOPICS = {
    eTPCS.ONLINE_STATE: f"{BASE_TOPIC}/online",

    eTPCS.SNAPSHOT_AVAIL: f"{BASE_TOPIC}/snapshot/available",
    eTPCS.SNAPSHOT_STATE: f"{BASE_TOPIC}/snapshot/state",
    eTPCS.SNAPSHOT_SET: f"{BASE_TOPIC}/snapshot/set",

    eTPCS.VIDEO_AVAIL: f"{BASE_TOPIC}/video/available",
    eTPCS.VIDEO_STATE: f"{BASE_TOPIC}/video/state",
    eTPCS.VIDEO_SET: f"{BASE_TOPIC}/video/set",

    eTPCS.HSTREAM_AVAIL: f"{BASE_TOPIC}/hstream/available",
    eTPCS.HSTREAM_STATE: f"{BASE_TOPIC}/hstream/state",
    eTPCS.HSTREAM_SET: f"{BASE_TOPIC}/hstream/set",

    eTPCS.USTREAM_AVAIL: f"{BASE_TOPIC}/ustream/available",
    eTPCS.USTREAM_STATE: f"{BASE_TOPIC}/ustream/state",
    eTPCS.USTREAM_SET: f"{BASE_TOPIC}/ustream/set",

    eTPCS.MOTIONENABLE_AVAIL: f"{BASE_TOPIC}/motionenabled/available",
    eTPCS.MOTIONENABLE_STATE: f"{BASE_TOPIC}/motionenabled/state",
    eTPCS.MOTIONENABLE_SET: f"{BASE_TOPIC}/motionenabled/set",

    eTPCS.PAN_AVAIL: f"{BASE_TOPIC}/pan/available",
    eTPCS.PAN_STATE: f"{BASE_TOPIC}/pan/state",
    eTPCS.PAN_SET: f"{BASE_TOPIC}/pan/set",

    eTPCS.PANA_AVAIL: f"{BASE_TOPIC}/pan_auto/available",
    eTPCS.PANA_STATE: f"{BASE_TOPIC}/pan_auto/state",
    eTPCS.PANA_SET: f"{BASE_TOPIC}/pan_auto/set",


    eTPCS.MOTION_AVAIL: f"{BASE_TOPIC}/motion/available",
    eTPCS.MOTION_STATE: f"{BASE_TOPIC}/motion",

    eTPCS.HASS_DISCOVERY_SNAPSHOT: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/snapshot/config",
    eTPCS.HASS_DISCOVERY_VIDEO: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/video/config",
    eTPCS.HASS_DISCOVERY_HSTREAM: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/httpstream/config",
    eTPCS.HASS_DISCOVERY_USTREAM: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/udpstream/config",
    eTPCS.HASS_DISCOVERY_MOTIONENABLE: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/motionenabled/config",
    eTPCS.HASS_DISCOVERY_MOTION: f"{HASS_DISCOVERY_PREFIX}/binary_sensor/{hostname}/motion/config",
    eTPCS.HASS_DISCOVERY_PAN: f"{HASS_DISCOVERY_PREFIX}/number/{hostname}/pan/config",
    eTPCS.HASS_DISCOVERY_PANA: f"{HASS_DISCOVERY_PREFIX}/switch/{hostname}/pan_auto/config"

}


def encode_json(value) -> str:
    return json.dumps(value)


class PiCam2Client (mqtt.Client):
    """ MQTT client class """

    def __init__(self, cfg) -> None:
        super().__init__(MQTT_CLIENT_ID)
        self.cfg = cfg
        self._mqtt_client = None
        self._update = False
        self._online = False
        self._video = False
        self._snapshot = False
        self._hstream = False
        self._ustream = False
        self._motionEnabled = True
        self._child = None
        self._panAngle = 0
        self._PanCam = None
        self.pana_active=False
        self.pan_semaphore = Semaphore()
        self.manufacturer = "unknown"
        self.swversion = "x.x"

        signal.signal(signal.SIGINT, self.daemon_kill)
        signal.signal(signal.SIGTERM, self.daemon_kill)

        info = getCameraInfo()
        logging.debug(str(info))
        if cfg.camera.index + 1 > len(info[0]):
            logging.error(
                f"camera index - but only {len(info[0])} camera(s) detected")
        else:
            self.model = info[0][cfg.camera.index].get("Model", "tbd")
            logging.info(
                f"configured camera model:{self.model} ,detected: {len(info[0])}")
            fnd = re.search("([vV][0-9][\S]+)", info[1])
            if fnd:
                self.swversion = fnd.group()
                logging.debug("SWVersion=" + self.swversion)

        if self.model.startswith("imx") or self.model.startswith("ov"):
            self.manufacturer = "Raspberry Pi"   

    def daemon_kill(self, *_args):
        self.client_down()
        logging.info(f"{MQTT_CLIENT_ID} MQTT daemon Goodbye!")
        exit(0)

    def checkNewPanCam(self):
        """
        check new PanCam instance required due to multiple Pan-Automation requests
        """
        if self.cfg.PAN.enabled and None==self._PanCam:
            self._PanCam = PanCam(self, self.cfg)
        
    def on_connect(self, _client, _userdata, _flags, rc):
        """
        on_connect when MQTT CleanSession=False (default) conn_ack will be send from broker
        """
        logging.debug(f"Connection returned result: {conn_ack(rc)}")
        self._online = True
        self.publish_hass()
        time.sleep(1)
        self.publish_avail_topics()
        time.sleep(1)
        self.publish_state_topics()
        time.sleep(1)
        self.subsribe_topics()
        
    def publish_avail_topics(self):
        for t in range(eTPCS.SNAPSHOT_AVAIL.value, eTPCS.END_AVAIL.value):
            self.publish_avail(eTPCS(t))
        self.publish_avail(eTPCS.MOTION_AVAIL, self._motionEnabled)

    def publish_state_topics(self):
        for t in range(eTPCS.SNAPSHOT_STATE.value, eTPCS.END_STATE.value):
            self.publish_state(eTPCS(t))
        self.publish_state(eTPCS.MOTION_STATE,
                           encode_json({"occupancy": False}))

    def subsribe_topics(self):
        for t in range(eTPCS.SNAPSHOT_SET.value, eTPCS.END_SET.value):
            self.subscribe(topic=TOPICS[eTPCS(t)], qos=QOS)

    def on_message(self, _client, _userdata, message):
        logging.debug(
            f" Received message  {str(message.payload) } on topic {message.topic} with QoS {str(message.qos)}")
        payload = str(message.payload.decode("utf-8"))
        
        if TOPICS[eTPCS.PAN_SET] == message.topic:
            logging.debug(f"Camera PAN request {payload}")
            self._panAngle = int(payload)
            self.checkNewPanCam()
            if self._PanCam and not self.pana_active:
                self.pan_semaphore.acquire()
                self._PanCam.rotate_to(self._panAngle)
                self.pan_semaphore.release()
                self.publish_state(eTPCS.PAN_STATE)  
        elif TOPICS[eTPCS.PANA_SET] == message.topic:
            logging.debug(f"Camera PAN Auto Motion {payload}")
            self.checkNewPanCam()
            if self._PanCam:
                if payload == "ON" and not self.pana_active:
                    self.pana_active=True
                    self._PanCam.start()
                    self.publish_state(eTPCS.PANA_STATE)
                elif payload == "OFF" and self.pana_active:
                    self._PanCam.trigger_stop()
                    #reset of active state by child_down
        
        elif message.topic == TOPICS[eTPCS.MOTIONENABLE_SET]:
            if payload == "ON":
                self._motionEnabled = True
                self.publish_state(eTPCS.MOTIONENABLE_STATE)
                self.publish_avail(eTPCS.MOTION_AVAIL)
            elif payload == "OFF":
                self._motionEnabled = False
                self.publish_state(eTPCS.MOTIONENABLE_STATE)
                self.publish_avail(eTPCS.MOTION_AVAIL, False)
                if self._child:  # # already active
                    self._child.trigger_stop()
            
        elif not self._child:
            if message.topic == TOPICS[eTPCS.SNAPSHOT_SET]:
                if payload == "ON":
                    self._child = ImageCapture(self, self.cfg, self._motionEnabled)
                    self._snapshot = True
                    self.publish_state(eTPCS.SNAPSHOT_STATE)
                    self._child.start()
            elif message.topic == TOPICS[eTPCS.VIDEO_SET]:
                if payload == "ON":
                    self._child = VideoCapture(self, self.cfg, self._motionEnabled)
                    self._video = True
                    self.publish_state(eTPCS.VIDEO_STATE)
                    self._child.start()
            elif message.topic == TOPICS[eTPCS.HSTREAM_SET]:
                if payload == "ON":
                    self._child = HTTPStreamCapture(self, self.cfg, self._motionEnabled)
                    self._hstream = True
                    self.publish_state(eTPCS.HSTREAM_STATE)
                    self._child.start()
            elif message.topic == TOPICS[eTPCS.USTREAM_SET]:
                if payload == "ON":
                    self._child = UDPStreamCapture(self, self.cfg, self._motionEnabled)
                    self._ustream = True
                    self.publish_state(eTPCS.USTREAM_STATE)
                    self._child.start()
            else:
                logging.warning("unhandled payload" + payload)
        else:
            if message.topic == TOPICS[eTPCS.SNAPSHOT_SET] and \
                    isinstance(self._child, ImageCapture):
                if payload == "OFF":
                    self._child.trigger_stop()
            elif message.topic == TOPICS[eTPCS.VIDEO_SET] and \
                    isinstance(self._child, VideoCapture):
                if payload == "OFF":
                    self._child.trigger_stop()
            elif message.topic == TOPICS[eTPCS.HSTREAM_SET] and \
                    isinstance(self._child, HTTPStreamCapture):
                if payload == "OFF":
                    self._child.trigger_stop()
            elif message.topic == TOPICS[eTPCS.USTREAM_SET] and \
                    isinstance(self._child, UDPStreamCapture):
                if payload == "OFF":
                    self._child.trigger_stop()
            else:
                logging.warning(f"Ignoring request {message.topic}:{payload}")

    def on_disconnect(self, _client, _userdata, rc=0):
        logging.debug("Broker disconnected: " + str(rc))
        self.loop_stop()

    # """
    # on_subscribe when SUB_ACK is send from broker due to client subscribe request
    # """
    # def on_subscribe(self, client, userdata, mid, qos):
    #     if isinstance(qos, list):
    #         qos_msg = str(qos[0])
    #     else:
    #         qos_msg = f"and granted QoS {qos[0]}"
    #     logging.debug(f"Subscribed {qos_msg}")

    # def on_log(self, client, userdata, level, buf):
    #    logging.info("on_log: "+buf)

    def client_down(self):
        """
        clean up everything when keyboard CTRL-C or daemon kill request occurs
        """
        for t in range(eTPCS.SNAPSHOT_AVAIL.value, eTPCS.END_AVAIL.value):
            self.publish_avail(eTPCS(t), False)
        
        self.publish_avail(eTPCS.MOTION_AVAIL, False)
        self._online = False
        self.publish_state(eTPCS.ONLINE_STATE)
        if self._PanCam:
            self._PanCam.reset_angle()
        self.disconnect()
        self.loop_stop()

    def child_down(self, child):
        """ callback function when picam2 threads stop """
        logging.debug("child_down received:" + str(child))
        
        if isinstance(child, ImageCapture):
            self._snapshot = False
            self.publish_state(eTPCS.SNAPSHOT_STATE)
            self._child = None
        elif isinstance(child, VideoCapture):
            self._video = False
            self.publish_state(eTPCS.VIDEO_STATE)
            self._child = None
        elif isinstance(child, HTTPStreamCapture):
            self._hstream = False
            self.publish_state(eTPCS.HSTREAM_STATE)
            self._child = None
        elif isinstance(child, UDPStreamCapture):
            self._ustream = False
            self.publish_state(eTPCS.USTREAM_STATE)
            self._child = None
        elif isinstance(child, PanCam):
            self.pana_active=False
            self._panAngle=child.get_angle()
            self.publish_state(eTPCS.PANA_STATE)
            self.publish_state(eTPCS.PAN_STATE)
            self._PanCam=None # delete old reference

    def motion_detected(self):
        """ callback function when motion has been detected """
        logging.debug("callback motion_detected")
        self.publish_state(eTPCS.MOTION_STATE,
                           encode_json({"occupancy": True}))
        time.sleep(0.5)
        self.publish_state(eTPCS.MOTION_STATE,
                           encode_json({"occupancy": False}))
    
    def pan_update(self,angle:int):
        """ callback function when PanCam has completed """
        logging.debug(f"callback pan_update:{angle}°")
        self._panAngle=angle
        self.publish_state(eTPCS.PAN_STATE)

    def publish_avail(self, msg: eTPCS, avail=True):
        """ publish avalibale topics """
        retain = RETAIN
        payload = None
        if msg.value >= eTPCS.SNAPSHOT_AVAIL.value or \
           msg.value < eTPCS.END_AVAIL.value or \
           msg == eTPCS.MOTION_AVAIL:
             
            payload = "online" if avail else "offline"

        if payload:
            self.publish(TOPICS[msg], payload, retain)
            logging.debug(f"publish {str(msg)}:{payload}")
        else:
            logging.warning(f"unhandled publish avail message:{TOPICS[msg]}")


    def publish_state(self, msg: eTPCS, payload=None):
        """ publish state topics """
        retain = RETAIN
        topic = TOPICS[msg]
        if eTPCS.ONLINE_STATE == msg:
            payload = self._online
        elif eTPCS.SNAPSHOT_STATE == msg:
            payload = "ON" if self._snapshot else "OFF"
        elif eTPCS.VIDEO_STATE == msg:
            payload = "ON" if self._video else "OFF"
        elif eTPCS.HSTREAM_STATE == msg:
            payload = "ON" if self._hstream else "OFF"
        elif eTPCS.USTREAM_STATE == msg:
            payload = "ON" if self._ustream else "OFF"
        elif eTPCS.MOTIONENABLE_STATE == msg:
            payload = "ON" if self._motionEnabled else "OFF"
        elif eTPCS.PANA_STATE == msg:
            payload = "ON" if self.pana_active else "OFF"
        elif eTPCS.PAN_STATE == msg:
            payload = self._panAngle

        if payload is not None:
            self.publish(topic, payload, retain)
            logging.debug(f"publish {str(msg)}:{payload}")
        else:
            logging.warning(f"unhandled publish state message:{TOPICS[msg]}")


    def publish_hass(self):
        """ 
        publish all homeassistant discovery topics
        """

        """     
            <discovery_prefix>/<component>/[<node_id>/]<object_id>/config
            https://www.home-assistant.io/integrations/mqtt#mqtt-discovery
            https://www.home-assistant.io/integrations/switch.mqtt/#configuration-variables
            allowed components: https://github.com/home-assistant/core/blob/dev/homeassistant/const.py
            https://www.home-assistant.io/docs/configuration/customizing-devices/#device-class
            https://www.home-assistant.io/integrations/switch.mqtt/
            https://developers.home-assistant.io/docs/device_registry_index/
    
        """
        logging.debug("publishing HASS discoveries")
        dev = {
                "identifiers":[f"{MQTT_CLIENT_ID}_{hostname}"],
                "manufacturer": self.manufacturer,
                "model": self.model,
                "sw_version": self.swversion,
                "name": f"{MQTT_CLIENT_ID}.{hostname}.PiCamera2"
            }
        config_snap = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.SNAPSHOT_AVAIL],
            "icon": "mdi:camera",
            "command_topic": TOPICS[eTPCS.SNAPSHOT_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/snapshot",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.SNAPSHOT_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.Snapshot"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_SNAPSHOT],
                     payload=encode_json(config_snap), retain=True)

        config_video = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.VIDEO_AVAIL],
            "icon": "mdi:file-video",
            "command_topic": TOPICS[eTPCS.VIDEO_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/video",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.VIDEO_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.Video"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_VIDEO],
                     payload=encode_json(config_video), retain=True)

        config_hstream = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.HSTREAM_AVAIL],
            "icon": "mdi:video",
            "command_topic": TOPICS[eTPCS.HSTREAM_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/httpstream",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.HSTREAM_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.HttpStream" 
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_HSTREAM],
                     payload=encode_json(config_hstream), retain=True)

        config_ustream = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.USTREAM_AVAIL],
            "icon": "mdi:video",
            "command_topic": TOPICS[eTPCS.USTREAM_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/udpstream",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.USTREAM_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.UdpStream"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_USTREAM],
                     payload=encode_json(config_ustream), retain=True)

        config_motionebl = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.MOTIONENABLE_AVAIL],
            "icon": "mdi:video",
            "command_topic": TOPICS[eTPCS.MOTIONENABLE_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/motionenabled",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.MOTIONENABLE_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.MotionEnabled"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_MOTIONENABLE],
                     payload=encode_json(config_motionebl), retain=True)

        config_motion = {
            "device": dev,
            "availability_topic": TOPICS[eTPCS.MOTION_AVAIL],
            "device_class": "motion",
            "icon": "mdi:motion-sensor",
            "json_attributes_topic": f"{MQTT_CLIENT_ID}/{hostname}/motion",
            "payload_off": False,
            "payload_on": True,
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/motion",
            "state_topic": f"{MQTT_CLIENT_ID}/{hostname}/motion",
            "name": f"{MQTT_CLIENT_ID}.{hostname}.Motion",
            "value_template": "{{ value_json.occupancy }}"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_MOTION],
                     payload=encode_json(config_motion), retain=True)
    
        config_pan = {
            "device": dev,
            "availability_topic": TOPICS[eTPCS.PAN_AVAIL],
            "device_class": "distance",
            "icon": "mdi:pan-horizontal",
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/pan",
            "state_topic": TOPICS[eTPCS.PAN_STATE],
            "command_template": "{{ value }}",
            "command_topic": TOPICS[eTPCS.PAN_SET],
            "unit_of_measurement":"°",
            "min":-90,
            "max":90,
            "step":1,
            "mode": "slider",
            "name": f"{MQTT_CLIENT_ID}.{hostname}.Pan",
            "value_template": "{{ value }}"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_PAN],
                     payload=encode_json(config_pan), retain=True)

        config_pana = {
            "device": dev,
            "device_class": "switch",
            "availability_topic": TOPICS[eTPCS.PANA_AVAIL],
            "icon": "mdi:pan-horizontal",
            "command_topic": TOPICS[eTPCS.PANA_SET],
            "unique_id": f"{MQTT_CLIENT_ID}/{hostname}/pan_automation",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_topic": TOPICS[eTPCS.PANA_STATE],
            "name": f"{MQTT_CLIENT_ID}.{hostname}.Pan-Automation"
        }
        self.publish(TOPICS[eTPCS.HASS_DISCOVERY_PANA],
                     payload=encode_json(config_pana), retain=True)

    def startup_client(self):
        """
        Start the MQTT client
        """
        logging.info(f'Starting up MQTT Service {MQTT_CLIENT_ID}')
        mqttattempts = 0
        while mqttattempts < self.cfg.MQTTBroker.connection_retries:
            try:
                self.username_pw_set(
                    self.cfg.MQTTBroker.username,
                    self.cfg.MQTTBroker.password)
                # no client certificate needed
                if len(self.cfg.MQTTBroker.clientcertfile) and \
                   len(self.cfg.MQTTBroker.clientkeyfile):
                    self.tls_set(certfile=self.cfg.MQTTBroker.clientcertfile, \
                                 keyfile=self.cfg.MQTTBroker.clientkeyfile, \
                                 cert_reqs=ssl.CERT_REQUIRED)
                else:
                    self.tls_set(cert_reqs=ssl.CERT_NONE)
                self.tls_insecure_set(self.cfg.MQTTBroker.insecure)
                self.connect(
                    self.cfg.MQTTBroker.host,
                    self.cfg.MQTTBroker.port)
                self.loop_start()
                # picam2client.setup(client,cfg)
                mqttattempts = self.cfg.MQTTBroker.connection_retries
            except BaseException as e:
                logging.error(
                    f"{str(e)}\nCould not establish MQTT Connection! Try again \
                    {str(self.cfg.MQTTBroker.connection_retries - mqttattempts)} xtimes")
                mqttattempts += 1
                if mqttattempts == self.cfg.MQTTBroker.connection_retries:
                    logging.error(
                        f"Could not connect to MQTT Broker {self.cfg.MQTTBroker.host} exit")
                    exit(-1)
                time.sleep(3)

        # main MQTT client loop
        while True:
            logging.debug(f"{MQTT_CLIENT_ID}-Loop")
            try:
                time.sleep(10)

            except KeyboardInterrupt:  # i.e. ctrl-c
                self.client_down()
                logging.info(f"{MQTT_CLIENT_ID} MQTT Goodbye!")
                exit(0)

            except Exception as e:
                logging.error(f"{MQTT_CLIENT_ID} exception:{str(e)}")
                self.disconnect()
                self.loop_stop()
                exit(-1)



def startClient(cfg: Config):
    """
    generator help function to create MQTT client instance  & start it
    """

    logging.basicConfig(level=LOG_LEVEL[cfg.LogLevel],
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%H:%M:%S')
    client = PiCam2Client(cfg)
    client.startup_client()
