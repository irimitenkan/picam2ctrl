#!/usr/bin/python3
# encoding: utf-8
import time
import TSL2591

sensor = TSL2591.TSL2591()
# sensor.SET_InterruptThreshold(0xff00, 0x0010)

while True:
    lux = sensor.Lux
    print('Total light: %d'%lux)
    sensor.TSL2591_SET_LuxInterrupt(50, 200)
    
    infrared = sensor.Read_Infrared
    print('Infrared light: %d'%infrared)
    visible = sensor.Read_Visible
    print('Visible light: %d'%visible)
    full_spectrum = sensor.Read_FullSpectrum
    print('Full spectrum (IR + visible) light: %d'%full_spectrum)
