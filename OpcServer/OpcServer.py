#!/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
#  File name: OpcServer.py
#  Virtual Environment: envOpcServer
#  Author: Poul Bezanson

import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd #https://pandas.pydata.org/pandas-docs/stable/index.html
import time
import datetime as dt
import threading 
import pandas as pd
import numpy as np
import sys

def ModBusConnector():
	# modbus connection initialization
	try:
		instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)
		instrument.serial.baudrate = 9600         # Baud
		instrument.serial.bytesize = 8
		instrument.serial.stopbits = 1
		instrument.serial.timeout  = 0.05          # seconds
		instrument.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
		instrument.clear_buffers_before_each_transaction = True
		print("[OK!] Connection established")
	except:
		print("[FAULT] Connection error")
		sys.exit()
	return instrument

def ModBusSpeedTester(connection):	
	# trаnsmission speed test
	#try:
	dList=ModBusReader(connection)
	TestParameters={"dTime": dList[1], "dList": dList}
	print(f"[OK!] The sensor polling time was (seconds) - {dList[1]:.6f}")
	#except:
	#	print("[FAULT] Sensor poll error")
	#	sys.exit()
	return TestParameters

def _ModBusReader(connection):
	beat.wait()
	CO2_value=110  # Registernumber, number of decimals
	TVOC_value=120
	PM1_0_value=130
	PM2_5_value=140
	PM10_value=150
	Temperature_value=160
	Humidity_value=170
	dTime_value=time.perf_counter()
	DataList.append([dTime_value,CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value])
	return dList

def ModBusReader(connection):
 ## Read parameters##
 #dt=time.perf_counter()-dt
 #beat.wait()
	Time_start=dt.datetime.now().timestamp()
	CO2_value=connection.read_register(0, 0, 4)  # Registernumber, number of decimals
	TVOC_value=connection.read_register(1, 2, 4)
	PM1_0_value=connection.read_register(2, 0, 4)
	PM2_5_value=connection.read_register(3, 0, 4)
	PM10_value=connection.read_register(4, 0, 4)
	Temperature_value=connection.read_register(5, 1, 4)
	Humidity_value=connection.read_register(6, 1, 4)
	Time_stop=dt.datetime.now().timestamp()
	dTime=round(Time_stop-Time_start,6)
	dList=[Time_start, dTime, CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value]
	return dList 
	
def ClockReader(dTime,FullTime,connection):
	t=0
	while t<FullTime:
		ModBusTread=threading.Thread(name='ModBusReading',target=ModBusReader, args=(connection,))
		ModBusTread.start()
		#beat.set()
		#beat.clear()
		time.sleep(dTime)
		t=t+dTime
	 
def DataFrameWrite():
	df=pd.DataFrame(columns=['CO2', 'TVOC', 'PM1.0', 'PM2.5', 'PM10', 'Temper', 'Humid'])

if __name__=="__main__":
	connection=ModBusConnector()
	parameters=ModBusSpeedTester(connection)
	#beat=threading.Event()
	ClockReader(0.5, 2, connection)

#!!! Нужно придумать как вернуть значение из потока	
#!!! Решение: https://superfastpython.com/thread-return-values/
  
 #for v in DataList: 
 # print(v)

	
