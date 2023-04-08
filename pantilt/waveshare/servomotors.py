'''
Created on 08.04.2023

@author: irimi
'''
import logging

from utils import ThreadEvent, Config
from pantilt.waveshare.PCA9685 import PCA9685 as Servos
from pantilt import PanTilt
from time import sleep

TILT = 0 # channel
PAN = 1  # channel

""" servos 0..180, but picam2ctrl range -90 .. 90"""
OFFSET = 90  
wtime = 0.001

WTIME ={
 "VERY_SLOW": wtime*200,
 "SLOW": wtime*100,
 "MEDIUM": wtime*60,    
 "FAST": wtime*30,
 "VERY_FAST": wtime*10    
}

class PanTiltServoMotors(PanTilt):
    """
    PAN & TILT camera with  2 servomotors 
    """
    def __repr__(self):
        return "PanTiltServoMotors" 

    def __init__(self,parent: ThreadEvent, cfg: Config):
        super().__init__(parent)
        logging.debug("init PanTiltServoMotors")

        self.servos = Servos()
        self.servos.setPWMFreq(50)
        #pwm.setServoPulse(1,500) 
        self.servos.setRotationAngle(PAN, OFFSET)
        self.servos.setRotationAngle(TILT, OFFSET)

        self.max_degree=cfg.PanTilt.Pan_angle_max
        self.pAngle = OFFSET
        self.tAngle = OFFSET
        self.wtime=WTIME.get(cfg.PanTilt.speed,WTIME["MEDIUM"])
    def pan_rotate_to(self,angle:int):
        logging.debug(f"PAN Rot_to from {self.pAngle} to {angle+OFFSET}")
        start=self.pAngle
        if start < angle+OFFSET:
            for _i in range(start,angle+OFFSET,1):
                if self.pAngle + 1 < 180:
                    self.pAngle=self.pAngle+1
                    self.servos.setRotationAngle(PAN,self.pAngle)
                    sleep(self.wtime)
                else:
                    break
        elif start > angle+OFFSET:
            for _i in range(start,angle+OFFSET,-1):
                if self.pAngle - 1 > 0:
                    self.pAngle=self.pAngle-1
                    self.servos.setRotationAngle(PAN,self.pAngle)
                    sleep(self.wtime)
                else:
                    break

    def tilt_rotate_to(self,angle:int):
        logging.debug(f"Tilt Rot_to from {self.tAngle} to {angle+OFFSET}")
        start=self.tAngle
        if self.tAngle < angle+OFFSET:
            for _i in range(start,angle+OFFSET,1):
                if self.tAngle + 1 < 180:
                    self.tAngle=self.tAngle+1
                    self.servos.setRotationAngle(TILT,self.tAngle)
                    sleep(self.wtime)
                else:
                    break
        elif self.tAngle > angle+OFFSET:
            for _i in range(start,angle+OFFSET,-1):
                if self.tAngle - 1 > 0:
                    self.tAngle=self.tAngle-1
                    self.servos.setRotationAngle(TILT,self.tAngle)
                    sleep(self.wtime)
                else:
                    break

    def get_panAngle(self) -> int:
        return self.pAngle-OFFSET
        
    def get_tiltAngle(self) -> int:
        return self.tAngle-OFFSET

    def resetAngles(self):
        logging.debug("resetAngles PanTiltServoMotors")
        self.pAngle=OFFSET
        self.servos.setRotationAngle(PAN,self.pAngle)
        self.tAngle=OFFSET
        self.servos.setRotationAngle(TILT,self.pAngle)
                
    def _worker_(self):
        """
        auto pan function
        """
        while not self._stopEvent.is_set(): 
            dest=self.max_degree
            if self.pAngle-OFFSET>0:
                dest=-dest
            
            self.pan_rotate_to(dest)
            self._parent.pan_update(dest)
        
    def _shutdown_(self):
        self.resetAngles()
        self.servos.exit_PCA9685()
        super()._shutdown_()
    