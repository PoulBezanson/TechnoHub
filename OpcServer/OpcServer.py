#!/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
#
#  File name: OpcServer.py
#  Virtual Environment: envOpcServer
#  Author: Poul Bezanson

import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd #https://pandas.pydata.org/pandas-docs/stable/index.html
import time

def ModBusReader():
 instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)
 #instrument.serial.port                     # this is the serial port name
 instrument.serial.baudrate = 9600          # Baud
 instrument.serial.bytesize = 8
 #instrument.serial.parity   = serial.PARITY_NONE
 instrument.serial.stopbits = 1
 instrument.serial.timeout  = 0.05          # seconds
 #instrument.address                         # this is the slave address number
 instrument.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
 instrument.clear_buffers_before_each_transaction = True
  
 ## Read parameters##
 SleepTime=0.1
 ReadTime=100
 CurrentTime=0
 dl=[]
 while CurrentTime<ReadTime:
  DTime=time.strftime("%Y.%m.%d %H:%M:%S.%f",time.localtime())
  CO2_value=instrument.read_register(0, 0, 4)  # Registernumber, number of decimals
  TVOC_value=instrument.read_register(1, 2, 4)
  PM1_0_value=instrument.read_register(2, 0, 4)
  PM2_5_value=instrument.read_register(3, 0, 4)
  PM10_value=instrument.read_register(4, 0, 4)
  Temperature_value=instrument.read_register(5, 1, 4)
  Humidity_value=instrument.read_register(6, 1, 4)
  print ([DTime, CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value])
  dl.append([DTime, CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value])
  time.sleep(SleepTime)
  CurrentTime=CurrentTime+SleepTime
 return(dl)
 
def DataFrameWrite():
 import pandas as pd
 df=pd.DataFrame(columns=['CO2', 'TVOC', 'PM1.0', 'PM2.5', 'PM10', 'Temper', 'Humid'])
 
if __name__=="__main__":
 dl=ModBusReader()
 #for y in dl:
 # print(y)
	
