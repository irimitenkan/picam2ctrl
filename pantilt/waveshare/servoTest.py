#!/usr/bin/python3
# encoding: utf-8
'''
Created on 07.04.2023

@author: irimi
'''
import time
from PCA9685 import PCA9685

print ("\nPCA9685 servo adjustment")
print ("========================\n")

print ("*** ATTENTION:  - this program must not be run when Pan-Tilt Hat is assembled completly ***" )
print ("*** ATTENTION:  - continue when only servos are connected Pan-Tilt hat  *** " )
print ("*** ATTENTION:  - i.e. BEFORE assembling to avoid damage of servos *** " )

val = input("to proceed with adjustment type 'yes':")
if "yes" == val:
    pwm = PCA9685(debug=False)
    print ("\n==========> PCA9685 servo adjustment starting ...\n")

    time.sleep(0.5)

    pwm.setPWMFreq(50)

    print ("\n==========> set angle to 0°\n")
    pwm.setRotationAngle(0, 0)
    pwm.setRotationAngle(1, 0)

    time.sleep(2)
    print ("\n==========> set angle to 180°\n")
    pwm.setRotationAngle(0, 180)
    pwm.setRotationAngle(1, 180)

    time.sleep(2)
    print ("\n==========> set angle to 0°\n")
    pwm.setRotationAngle(0, 0)
    pwm.setRotationAngle(1, 0)

    time.sleep(3)

    pwm.exit_PCA9685()

    print ("\n==========> PCA9685 servo adjustment completed")
else:
    print ("canceled")
