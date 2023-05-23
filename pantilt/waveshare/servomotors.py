'''
Created on 08.04.2023

@author: irimi
'''
import logging

from utils import ThreadEvent
from config import Config
from pantilt.waveshare.PCA9685 import PCA9685 as Servos
from pantilt import PanTilt
from time import sleep

TILT = 0 # channel
PAN = 1  # channel

""" servos 0..180, but picam2ctrl range -90 .. 90"""

SERVO_MAX = 180
SERVO_OFFSET = 90
wtime = 0.001

WTIME ={
 "VERY_SLOW": wtime*150,
 "SLOW": wtime*130,
 "MEDIUM": wtime*100,
 "FAST": wtime*80,
 "VERY_FAST": wtime*40
}

class PanTiltServoMotors(PanTilt):
    """
    PAN & TILT camera with 2 servomotors
    """
    def __repr__(self):
        return "PanTiltServoMotors" 

    def __init__(self,parent: ThreadEvent, cfg: Config, offset=SERVO_OFFSET):
        super().__init__(parent,(cfg.PanTilt.Pan.angle_min,cfg.PanTilt.Pan.angle_max),offset)
        logging.debug("init PanTiltServoMotors")

        self.servos = Servos()
        self.servos.setPWMFreq(50)
        #pwm.setServoPulse(1,500) 
        self.servos.setRotationAngle(PAN,SERVO_OFFSET )
        self.servos.setRotationAngle(TILT,SERVO_OFFSET)

        self.wtime=WTIME.get(cfg.PanTilt.speed,WTIME["MEDIUM"])

    def _pan_rotate_to_(self):
        angle=self._panDest
        logging.debug(f"PAN Rot_to from {self.pAngle} to {angle+self.Offset}")
        start=self.pAngle
        if start < angle+self.Offset:
            for _i in range(start,angle+self.Offset,1):
                if self.pAngle + 1 < SERVO_MAX:
                    self.pAngle=self.pAngle+1
                    self.servos.setRotationAngle(PAN,self.pAngle)
                    sleep(self.wtime)
                else:
                    break
        elif start > angle+self.Offset:
            for _i in range(start,angle+self.Offset,-1):
                if self.pAngle - 1 > 0:
                    self.pAngle=self.pAngle-1
                    self.servos.setRotationAngle(PAN,self.pAngle)
                    sleep(self.wtime)
                else:
                    break

    def _tilt_rotate_to_(self):
        angle=self._tiltDest
        logging.debug(f"Tilt Rot_to from {self.tAngle} to {angle+self.Offset}")
        start=self.tAngle
        if self.tAngle < angle+self.Offset:
            for _i in range(start,angle+self.Offset,1):
                if self.tAngle + 1 < SERVO_MAX:
                    self.tAngle=self.tAngle+1
                    self.servos.setRotationAngle(TILT,self.tAngle)
                    sleep(self.wtime)
                else:
                    break
        elif self.tAngle > angle+self.Offset:
            for _i in range(start,angle+self.Offset,-1):
                if self.tAngle - 1 > 0:
                    self.tAngle=self.tAngle-1
                    self.servos.setRotationAngle(TILT,self.tAngle)
                    sleep(self.wtime)
                else:
                    break

    def resetAngles(self):
        logging.debug("resetAngles PanTiltServoMotors")
        self.pAngle=self.Offset
        self.servos.setRotationAngle(PAN,self.pAngle)
        self.tAngle=self.Offset
        self.servos.setRotationAngle(TILT,self.pAngle)

    def _shutdown_(self):
        self.resetAngles()
        self.servos.exit_PCA9685()
        super()._shutdown_()
