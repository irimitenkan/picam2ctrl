from utils import ThreadEvent
from threading import Event
import logging

class PanTilt(ThreadEvent):
    def __init__(self, parent=None, max_angles=(-180,180), offset=0):
        super().__init__(parent)
        self._rotEvent = Event()

        self._panTo=False
        self._tiltTo=False
        self._autoPan=False
        self._panDest=0
        self._tiltDest=0

        #actuall pan angle
        self.pAngle = offset
        #actuall tilt angle
        self.tAngle = offset

        self.Offset=offset
        #maximum abs(angle)
        self.min_angle=max_angles[0]
        self.max_angle=max_angles[1]

    def _worker_(self):
        """
        trigger pan tilt rotation
        """
        logging.debug(" -> PanTilt._worker_ started")
        while not self._stopEvent.is_set():
            self._rotEvent.wait()
            logging.debug("PanTiltServoMotors rotEvent active")
            if self._autoPan:
                logging.debug("PanTiltServoMotors rotEvent autopan")
                self._panDest=self.max_angle
                if self.get_panAngle()>0:
                    self._panDest=self.min_angle

                self._pan_rotate_to_()
                self._parent.pan_update(self.get_panAngle())
                if not self._autoPan: # disable event
                    self.resetAngles()
                    self._parent.pan_update(self.get_panAngle())
            elif self._panTo:
                logging.debug("PanTiltServoMotors rotEvent panto")
                self._pan_rotate_to_()
                self._panTo=False
                self._rotEvent.clear()
                self._parent.pan_update(self.get_panAngle())

            if self._tiltTo:
                logging.debug("PanTiltServoMotors rotEvent tiltto")
                self._tilt_rotate_to_()
                self._tiltTo=False
                if not self._autoPan:
                    self._rotEvent.clear()
                self._parent.tilt_update(self.get_tiltAngle())

    def pan_rotate_to(self,angle:int):
        self._panDest=angle
        self._panTo=True
        self._rotEvent.set()
        logging.debug(f"pantilt.pan_rotate_to:{angle}")

    def pan_rotate_auto(self, enable:bool):
        if enable:
            self._autoPan=True
            self._rotEvent.set()
        else:
            self._autoPan=False
            self._rotEvent.clear()

        logging.debug(f"pantilt.pan_rotate_auto on/off:{self._autoPan}")

    def tilt_rotate_to(self,angle:int):
        self._tiltDest=angle
        self._tiltTo=True
        self._rotEvent.set()
        logging.debug(f"pantilt.tilt_rotate_to:{angle}")

    def _tilt_rotate_to_(self):
        pass

    def _pan_rotate_to_(self):
        pass

    def get_Pana_active(self)-> bool:
        return self._autoPan

    def get_panAngle(self) -> int:
        return self.pAngle-self.Offset

    def get_tiltAngle(self) -> int:
        return self.tAngle-self.Offset

    def resetAngles(self):
        pass

    def trigger_stop(self):
        super().trigger_stop()
        self._rotEvent.set()
