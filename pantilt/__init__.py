from utils import ThreadEvent

class PanTilt(ThreadEvent):
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def pan_rotate_to(self,angle:int):
        pass

    def pan_rotate_auto(self):
        pass
    
    def tilt_rotate_to(self,angle:int):
        pass
    
    def tilt_rotate_auto(self):
        pass

    def get_panAngle(self) -> int:
        pass

    def get_tiltAngle(self) -> int:
        pass

    def resetAngles(self):
        pass
        