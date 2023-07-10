#/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------
# The program generates a time series of atmospheric parameter 
# vectors read from the sensor, which is connected to the 
# microcontroller via the modbus bus.
# file name: OpcServer.py
# virtual environment: envOpcServer
# author: Poul Bezanson
# email:

import sys
sys.path.insert(0, "/home/orangepi/projects/TechnoHub/Devices/modules/")
#import keyboard
from pynput import keyboard
import time
import threading 
import class1_QualityMonitor as dv

def on_key(key):
	if key == keyboard.Key.esc:
		device_1.set_status_device('offline')

if __name__=="__main__":
	device_1=dv.Device() 
	listener = keyboard.Listener(on_release=on_key)
	listener.start()
	while device_1.get_status_device()=='None':
		#print('1')
		print(keyboard.is_pressed('a'))
		#print(device_1.get_status_device())
	print(device_1.get_status_device())
	
