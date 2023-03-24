#!/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
#  File name: OpcServer.py
#  Virtual Environment: envOpcServer
#  Author: Poul Bezanson

import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd #https://pandas.pydata.org/pandas-docs/stable/index.html
import time
import threading 
import pandas as pd

def ModBusReader():
 ## Read parameters##
 #dt=time.perf_counter()-dt
 beat.wait()
 CO2_value=instrument.read_register(0, 0, 4)  # Registernumber, number of decimals
 TVOC_value=instrument.read_register(1, 2, 4)
 PM1_0_value=instrument.read_register(2, 0, 4)
 PM2_5_value=instrument.read_register(3, 0, 4)
 PM10_value=instrument.read_register(4, 0, 4)
 Temperature_value=instrument.read_register(5, 1, 4)
 Humidity_value=instrument.read_register(6, 1, 4)
 dTime_value=time.perf_counter()
 #DTime=time.strftime("%Y.%m.%d %H:%M:%S",time.localtime())
 DataList.append([dTime_value,CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value])
 return(DataList)

def ClockEvent(dTime,FullTime):
 i=0
 while i<FullTime:
  ModeBusTread=threading.Thread(name='ModBusReading',target=ModBusReader)
  ModeBusTread.start()
  beat.set()
  beat.clear()
  time.sleep(dTime)
  i=i+1
 
def DataFrameWrite():
 
 df=pd.DataFrame(columns=['CO2', 'TVOC', 'PM1.0', 'PM2.5', 'PM10', 'Temper', 'Humid'])

if __name__=="__main__":
  
 # initialization of the modbus connection
 instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)
 instrument.serial.baudrate = 9600         # Baud
 instrument.serial.bytesize = 8
 instrument.serial.stopbits = 1
 instrument.serial.timeout  = 0.05          # seconds
 instrument.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
 instrument.clear_buffers_before_each_transaction = True
  
 # initialization of the time and frequency of polling the sensor
 DataList=[]
 #dTime_value=[]; CO2_value=[]; TVOC_value=[]; PM1_0_value=[]; PM2_5_value=[]; PM10_value=[]; Temperature_value=[]; Humidity_value=[]
 beat=threading.Event()
 dTime=0.3
 FullTime=10
 dl=ClockEvent(dTime,FullTime)
 
 for y in DataList:
  print(y)

	
