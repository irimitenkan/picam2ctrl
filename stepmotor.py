'''
Created on 17.03.2023

@author: irimi
'''
from time import sleep
from gpiozero import OutputDevice as Pin
import logging

# time setup for stepmotor movement
wtime = 0.001
ANGLE_FULL=512
#ANGLE_MAX=int(ANGLE_FULL/4)
ANGLE_STEP=int(ANGLE_FULL/64)
ANGLE_AUTO=int(ANGLE_FULL/8)

WTIME ={
 "VERY_SLOW": wtime*20,
 "SLOW": wtime*15,
 "MEDIUM": wtime*10,    
 "FAST": wtime*5,
 "VERY_FAST": wtime    
}

# class Pin:
#     def __init__(self,port:int):
#         self.port=port
#
#     def on(self):
#         pass
#
#     def off(self):
#         pass
    
class StepMotor (object):
    """
    StepMotor class designed for 
    
    28BYJ-48: 5V Stepper Motor + 
    ULN2003 driver board (with LEDS labled A,B,C,D) 
    """
    
    ROT_SEQ = [ 
             [0,0,0,1], 
             [0,0,1,1],
             [0,0,1,0],
             [0,1,1,0],
             [0,1,0,0],
             [1,1,0,0],
             [1,0,0,0],
             [1,0,0,1]
             ]
        
    def __init__(self, GPIO_A:int,
                       GPIO_B:int,
                       GPIO_C:int,
                       GPIO_D:int,
                       MAX_ANGLE:int,
                       speed: str):
        """
        create a StepMotor instance
        
        @param GPIO_A: connected GPIO Pin with LED 'A' 
        @param GPIO_B: connected GPIO Pin with LED 'B'
        @param GPIO_C: connected GPIO Pin with LED 'C'
        @param GPIO_C: connected GPIO Pin with LED 'D'
        @param MAX_ANGLE: max angle in degrees to rotate left(<0°) or right (>0°)
        @param speed: string LOW, MEDIUM, FAST to define the step motor rotation speed  
        
        connected GPIO pins / specific wiring:
        see LED labels A-D on ULN2003 driver board
        use StepMotor.test() to verify your GPIO wiring 
        """
        self._angle=0
        self.ANGLE_MAX=int(MAX_ANGLE*ANGLE_FULL/360)
        self.PinA=Pin(GPIO_A)
        self.PinB=Pin(GPIO_B)
        self.PinC=Pin(GPIO_C)
        self.PinD=Pin(GPIO_D)
        self.PINS=[self.PinA,self.PinB,self.PinC,self.PinD]
        self.wtime=WTIME.get(speed,wtime*5)
        logging.debug (f"Creating StepMotor max angle +-{self.ANGLE_MAX}/{ANGLE_FULL}, wtime = {self.wtime}")
        
    def rotate_to (self,degree :int):
        """
        rotate the step motor to a defined angle   
        @param degrees: +- destinaton angle to rotate in degrees
        """
        dest=int(ANGLE_FULL*degree/360)
        logging.debug(f"rotate_to {dest}")
        if abs(dest)>self.ANGLE_MAX:
            logging.warning(f"angle out of bounds {int(self.ANGLE_MAX*360/ANGLE_FULL)}: {degree}")
        else:
            if self._angle <= 0:
                diff=degree+abs(self.get_angle())
            else :
                diff=degree-abs(self.get_angle())
                
            self.rotate(diff)
            
            
    def rotate (self,degree : int ):
        """
        rotate the step motor left/right   
        @param degrees: +- angle to rotate in degrees
        """

        diff=int(ANGLE_FULL*degree/360)
        if degree>0:
            self._rot_right_(diff)
        else:
            self._rot_left_(diff)
    
    def _rot_right_(self, steps: int):
        """
        rotate right (ANGLE_FULL based)
        @param steps: how many steps to rotate right,
                      1 step = 360 / 512  
        """
        logging.debug(f"rotate right: {steps}")
        for _ in range (abs(steps)):
            if (self._angle+1>self.ANGLE_MAX):
                logging.warning(f"Max angle exceeded: {self.ANGLE_MAX}")
                break
            else:
                self._angle=self._angle+1
                for step in self.ROT_SEQ:
                    self._step_(step)

        logging.debug(f"actual angle {self._angle}")
        
    def _rot_left_(self, steps: int):
        """
        rotate left (ANGLE_FULL based) 
        @param steps: how many steps to rotate left, 1 step = 360° / 512  
        """
        logging.debug(f"rotate left: {steps}")
        for _ in range (abs(steps)):
            if (self._angle-1<-self.ANGLE_MAX):
                logging.warning(f"Max angle exceeded: -{self.ANGLE_MAX}")
                break
            else:
                self._angle=self._angle-1
                for step in reversed(self.ROT_SEQ):
                    self._step_(step)

        logging.debug(f"actual angle {self._angle}")
    
    def _step_(self,step: list):
        """ single sequence rotation step: 1/512"""
        for idx, pin in enumerate(self.PINS):
            if step[idx]: pin.on() 
        sleep (self.wtime)
        for pin in self.PINS:
            pin.off()
        
    
    def reset_angle(self, speed=wtime):
        """
        reset step motor to 0° (as started) 
        """
        old=self.wtime
        self.wtime=wtime
        logging.debug("reset rot to 0")
        if self._angle<0:
            self._rot_right_(-self._angle)
        elif self._angle > 0:
            self._rot_left_(-self._angle)
        self.wtime=old
        
    def testPins(self):
        """ LED pin  / GPIO connection test 
            visual check to verify GPIO port assignment and wiring: 
            flash on/off LEDs A->B->C->D 
        """
        logging.debug(f"flashing LED A->B->C->D check")
        self._testPin_(self.PinA)
        self._testPin_(self.PinB)
        self._testPin_(self.PinC)
        self._testPin_(self.PinD)

    
    def get_angle(self)-> int:
        """
        get the actual PAN angle of motor in degrees
        @return: the PAN angle in degrees
        """
        a=int(self._angle*360/ANGLE_FULL)
        logging.debug(f"getting actual angle: {a}°")
        return a 

    def check(self):
        """ 
        simple rotation test
        """
        logging.debug(f"simple motor rotation test")
        self.rotate(90)
        self.rotate(-180)
        self.rotate(90)

    def _testPin_(self,pin: Pin):
        """ 
        switch on/off one single GPIO Pin
        """
        pin.on()
        sleep(0.3)
        pin.off()



#some basic tests            
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%H:%M:%S')

    sm = StepMotor(27,22,23,24,90,"VERY_SLOW")
    sm.testPins()
    sm.check()
        