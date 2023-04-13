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
        super().__init__(parent,cfg.PanTilt.Pan_angle_max)

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
            self.TiltMotor=StepMotor(cfg.PanTilt.ULN2003.Tilt_GPIO_PinA,
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinB,
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinC,
                                     cfg.PanTilt.ULN2003.Tilt_GPIO_PinD,
                                     cfg.PanTilt.Tilt_angle_max,
                                     cfg.PanTilt.speed)
            if cfg.PanTilt.ULN2003.check:
                self.TiltMotor.testPins()
        else:
            self.TiltMotor=None

        #self.max_degree=cfg.PanTilt.Pan_angle_max
        self.triggered=False
    
    def _pan_rotate_to_(self):
        if self.PanMotor:
            self.PanMotor.rotate_to(self._panDest)

    def _tilt_rotate_to_(self):
        if self.TiltMotor:
            self.TiltMotor.rotate_to(self._tiltDest)

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
        
    def _shutdown_(self):
        self.resetAngles()
        super()._shutdown_()
    