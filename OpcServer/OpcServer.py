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

import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd #https://pandas.pydata.org/pandas-docs/stable/index.html
import time
import datetime as dt
import threading 
import pandas as pd
import numpy as np
import sys
import mysql.connector

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
	except:
		print("[FAULT!] Sensor connection error")
		sys.exit()
	else:
		print("[OK!] Sensor connection established")
	return instrument

def ModBusSpeedTester(_connection):	
	# trаnsmission speed test
	#try:
	BeatEvent.set()
	ModBusRead(_connection)
	BeatEvent.clear()
	TestParameters={"dTime": DataList[0][1], "dList": DataList[0]}
	Speed=TestParameters["dTime"]
	print(f"[OK!] The sensor polling time was (seconds) - {Speed:.6f}")
	DataList.pop()
	#except:
	#	print("[FAULT] Sensor poll error")
	#	sys.exit()
	return TestParameters
	
def ModBusRead(_connection):
	BeatEvent.wait()
	Time_start=dt.datetime.now().timestamp()
	CO2_value=_connection.read_register(0, 0, 4)  # Registernumber, number of decimals
	TVOC_value=_connection.read_register(1, 2, 4)
	PM1_0_value=_connection.read_register(2, 0, 4)
	PM2_5_value=_connection.read_register(3, 0, 4)
	PM10_value=_connection.read_register(4, 0, 4)
	Temperature_value=_connection.read_register(5, 1, 4)
	Humidity_value=_connection.read_register(6, 1, 4)
	Time_stop=dt.datetime.now().timestamp()
	dTime=round(Time_stop-Time_start,6)
	DataList.append([Time_start, dTime, CO2_value, TVOC_value, PM1_0_value, PM2_5_value, PM10_value, Temperature_value, Humidity_value])
	BeatEvent.clear()
	
def TimeSleep(_dTime):
	BeatEvent.set()
	time.sleep(_dTime)
			
def ClockReader(_dTime,_FullTime,_MbConnection):
	t=0
	while t<_FullTime:
		ModBusReadTread=threading.Thread(name='ModBusReadTread',target=ModBusRead, args=(_MbConnection,))
		TimeSleepTread=threading.Thread(name='TimeSleepTread',target=TimeSleep, args=(_dTime,))
		ModBusReadTread.start()
		TimeSleepTread.start()
		TimeSleepTread.join()
		t=t+_dTime
			 
def WriteListToDB(_DataList):
	# connect to MySQL DB
	try:
		DbConnection=mysql.connector.connect(
		host="192.168.0.113",
		user="orangepi",
		password="orangepi",
		database="datasets"
		)
		if DbConnection.is_connected():
			print("[OK!] Connected to MySQL database")
	except:
		print("[FAULT!] Data Base connection error")
		sys.exit()
	# write DataList to MySql DB	
	query="INSERT INTO aqm_dataset (Time, dTime, CO2, TVOC, PM1_0, PM2_5, PM10, Temperature, Humidity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
	cursor=DbConnection.cursor()    
	cursor.executemany(query, _DataList)
	DbConnection.commit()
	print("[OK!] Record inserted successfully into table")    
	# Close MySQL connection
	if DbConnection.is_connected():
		cursor.close()
		DbConnection.close()
		print("[OK!] MySQL connection is closed")
         
if __name__=="__main__":
	DataList=[]
	MbConnection=ModBusConnector()
	BeatEvent=threading.Event()
	parameters=ModBusSpeedTester(MbConnection)
	dTime=0.5
	FullTime=2
	ClockReader(dTime, FullTime, MbConnection)
	for v in DataList: 
		print(v)
	WriteListToDB(DataList)
#	_df=pd.DataFrame(data=_DataList, index=None, columns=['Time', 'dTime', 'CO2', 'TVOC', 'PM1_0', 'PM2_5', 'PM10', 'Temperature', 'Humidity'])
#	_df.to_sql(name="aqm_dataset",con=mydb, schema='datasets', if_exists='append', index=False)
#	print(df)
	
