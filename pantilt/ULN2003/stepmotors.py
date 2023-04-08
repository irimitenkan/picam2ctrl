'''
Created on 05.04.2023

@author: irimi
'''

from utils import ThreadEvent, Config
from pantilt.ULN2003.stepmotor import StepMotor
from pantilt import PanTilt

class PanTiltStepMotors(PanTilt):
    """
    PAN and/or TILT camera with  1 or 2 stepmotors 
    """
    def __repr__(self):
        return "PanTiltStepMotors" 

    def __init__(self,parent: ThreadEvent, cfg: Config):
        super().__init__(parent)

        # PAN - Motor
        if cfg.PanTilt.ULN2003.Pan_enabled:
            self.PanMotor=StepMotor(cfg.PanTilt.ULN2003.Pan_GPIO_PinA, 
                                     cfg.PanTilt.ULN2003.Pan_GPIO_PinB,
                                     cfg.PanTilt.ULN2003.Pan_GPIO_PinC,
                                     cfg.PanTilt.ULN2003.Pan_GPIO_PinD,
                                     cfg.PanTilt.Pan_angle_max,
                                     cfg.PanTilt.speed)
            if cfg.PanTilt.ULN2003.check:
                self.PanMotor.testPins()
        else:
            self.PanMotor=None
        # TILT-Motor
        if cfg.PanTilt.ULN2003.Tilt_enabled:
            self.PanMotor=StepMotor(cfg.PanTilt.ULN2003.Pan_GPIO_PinA, 
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinB,
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinC,
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinD,
                                     cfg.PanTilt.Tilt_angle_max,
                                     cfg.PanTilt.speed)
            if cfg.PanTilt.ULN2003.check:
                self.TiltMotor.testPins()
        else:
            self.TiltMotor=None

        self.max_degree=cfg.PanTilt.Pan_angle_max
        self.triggered=False
    
    def pan_rotate_to(self,angle:int):
        if self.PanMotor:
            self.PanMotor.rotate_to(angle)

    def tilt_rotate_to(self,angle:int):
        if self.TiltMotor:
            self.TiltMotor.rotate_to(angle)

    def get_panAngle(self) -> int:
        if self.PanMotor:
            return self.PanMotor.get_angle()
        else:
            return 0
        
    def get_tiltAngle(self) -> int:
        if self.TiltMotor:
            return self.TiltMotor.get_angle()
        else:
            return 0

    def resetAngles(self):
        if self.PanMotor:
            self.PanMotor.reset_angle()

        if self.TiltMotor:
            self.TiltMotor.reset_angle()
        
                
    def _worker_(self):
        """
        auto pan function
        """
        if self.PanMotor:
            while not self._stopEvent.is_set(): 
                dest=self.max_degree
                if self.PanMotor.get_angle()>0:
                    dest=-dest
                
                self.pan_rotate_to(dest)
                self._parent.pan_update(dest)
        
    def _shutdown_(self):
        if self.PanMotor:
            self.PanMotor.reset_angle()
        super()._shutdown_()
    