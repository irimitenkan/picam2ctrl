'''
Created on 08.04.2023

@author: irimi
'''
from pantilt.waveshare.TSL2591 import TSL2591
from utils import ThreadEvent
from time import sleep

class LightSensor(ThreadEvent):
    def __init__(self, parent=None, timeout=60):
        super().__init__(parent)
        
        self.timeout=timeout
        self.sensor = TSL2591()

    def _worker_(self):
        """
        update light
        """
        while not self._stopEvent.is_set(): 
            lux = self.sensor.Lux
            if self._parent:
                self._parent.light_update(lux)
            sleep(self.timeout)
            self.sensor.TSL2591_SET_LuxInterrupt(50, 200)

    def _shutdown_(self):
        self.sensor.CleanUp()
        super()._shutdown_()
            