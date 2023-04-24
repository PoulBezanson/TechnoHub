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
flag_read_data=threading.Event()

class Device_1:
	'''
	Описывет датчик измерения параметров микроклимата
	'''
	def __init__(self):
		'''конструктор'''
		self.d_time=1 # время дискретизации измеряемого процесса (сек.) 
		self.full_time=3 # длительность эксперимента (сек.)
		self.time_init=10 # предельная длительность инициализации начального состояния (сек.)
		self.connection_device=None # экземпляр класса устройства modbus
		self.data_series=[]
		self.connection_database=None
		self.cursor_database=None
		self.parameters={"id_experiment": None, \
						 "time_start": None, \
						 "time_finish": None, \
						 "mute_state": None, \
						 "unit_state": None}
			
	def connect_to_device(self):
		'''
		Инициализировать связь с устройством. 
		'''
		try:
			self.connection_device = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)
			self.connection_device.serial.baudrate = 9600         # Baud
			self.connection_device.serial.bytesize = 8
			self.connection_device.serial.stopbits = 1
			self.connection_device.serial.timeout  = 0.1          # seconds
			self.connection_device.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
			self.connection_device.clear_buffers_before_each_transaction = True
		except:
			print("[FAULT!] connect_to_device(): Sensor connection error")
			return 0
		else:
			print("[OK!] connect_to_device(): Successful connection with the device")
			return self.connection_device
	
	def disconnect_from_device(self):
		'''инициализирует разрыв связи с устройством'''
		pass
	
	def get_reading_speed(self):
		'''
		Тестировать скорость считывания данных устройства
		Возвращает время разового опроса параметров остройства
		'''
		flag_read_data.set()
		self.__read_data()
		flag_read_data.clear()
		s_time=self.data_series[0][1]-self.data_series[0][0]
		print(f"[OK!] get_reading_speed(): The sensor polling time was (seconds) - {s_time:.6f}")
		self.data_series.pop()
		return s_time
	
	def __read_data(self):
		'''
		Читать вектор данных из устройства.
		'''
		flag_read_data.wait()
		time_start=dt.datetime.now().timestamp()
		CO2=self.connection_device.read_register(registeraddress=0, number_of_decimals=0, functioncode=4)  # Registernumber, number of decimals
		TVOC=self.connection_device.read_register(registeraddress=1, number_of_decimals=2, functioncode=4)
		PM1_0=self.connection_device.read_register(registeraddress=2, number_of_decimals=0, functioncode=4)
		PM2_5=self.connection_device.read_register(registeraddress=3, number_of_decimals=0, functioncode=4)
		PM10=self.connection_device.read_register(registeraddress=4, number_of_decimals=0, functioncode=4)
		Temperature=self.connection_device.read_register(registeraddress=5, number_of_decimals=1, functioncode=4)
		Humidity=self.connection_device.read_register(registeraddress=6, number_of_decimals=1, functioncode=4)
		time_finish=dt.datetime.now().timestamp()
		self.data_series.append([time_start, time_finish, CO2, TVOC, PM1_0, PM2_5, PM10, Temperature, Humidity])
		flag_read_data.clear()
	
	def read_data_series(self):
		'''
		Читать временной ряд данных из устройства.
		'''
		t=0
		while t<self.full_time:
			read_data_thread=threading.Thread(name='read_data_thread',target=self.__read_data)
			holdup_time_thread=threading.Thread(name='holdup_time_thread',target=self.__holdup_time)
			read_data_thread.start()
			holdup_time_thread.start()
			holdup_time_thread.join()
			t=t+self.d_time
		print(f"[ОК!] read_data_series(): Data series read successfully: dTime={self.d_time}, FullTime={self.full_time}")
		return 1

	def __holdup_time(self):
		'''удержать время на единицу дискретизации'''
		flag_read_data.set()
		time.sleep(self.d_time)
			
	def clear_data_series(self):
		'''отчистить значения временного ряда'''
		self.data_series=[]
		print("[ОК!] clear_data_series(): Data series cleared")
		return 1
	
	def print_data_series(self):
		'''напечатать значения временного ряда '''
		print("[ОК!] print_data_series(): Data series:")
		for v in self.data_series:
			print(v)
		
	def connect_to_database(self):
		'''инициализировать соединение с базой данных'''
		try:
			self.connection_database=mysql.connector.connect(
			host="192.168.0.113",
			user="orangepi",
			password="orangepi",
			database="device_1"
			)
			self.cursor_database=self.connection_database.cursor()    
			if self.connection_database.is_connected():
				print("[OK!] connect_to_database(): Connected to MySQL database")
				return self.connection_database
		except:
			print("[FAULT!] connect_to_database(): Data Base connection error")
			return 0
	
	def disconnect_from_database(self):
		'''разорвать соединение с базой данных'''
		if self.connection_database.is_connected():
			self.cursor_database.close()
			self.connection_database.close()
			print("[OK!] disconnect_from_database(): MySQL connection is closed")
	
	def write_db_data_series(self):
		'''разорвать соединение с базой данных'''
		query="INSERT INTO d1_data_series (time_start, time_finish, CO2, TVOC, PM1_0, PM2_5, PM10, Temperature, Humidity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);"
		self.cursor_database.executemany(query, self.data_series)
		self.connection_database.commit()
		print("[OK!] write_db_data_series(): Record inserted successfully into database table")  

	def set_initial_state(self):
		'''привести объект в начальное состояние и контролировать приведение'''
		init_state={"mute_state": 0, "unit_state": 1}
		# преобразование mute_state и unit_state в битовое поле 
		reg17_state=init_state["mute_state"] | (init_state["unit_state"]<<1)
		#self.connection_device.write_register(registeraddress=16, value=init_state["backlight"], number_of_decimals=0, functioncode=6)
		self.connection_device.write_register(registeraddress=17, value=reg17_state, number_of_decimals=0, functioncode=6)
		# контроль приведения в начальное состояние
		flag_init=0
		t=0
		while (t < self.time_init) and (flag_init==0):
			backlight=self.connection_device.read_register(registeraddress=16, number_of_decimals=0, functioncode=3)
			if backlight==2:
				print(f"[ОК!] set_initial_state(): Device initialization done")
				flag_init=1
				return 1
			time.sleep(1)
			t=t+1
		print(f"[FAULT!] set_initial_state(): Device initialization problem")
		return 0
		
	def push_parameters_to_device(self):
		'''отправить вектор параметров экспериментана на устройство'''
		reg17_state=self.parameters["mute_state"] | (self.parameters["unit_state"]<<1)
		self.connection_device.write_register(registeraddress=17, value=reg17_state, number_of_decimals=0, functioncode=6)
		print("[ОК!] push_parameters_to_device(): Parameter vector sent to device")
		return 1
		
	def read_db_parameters(self):
		'''
		Читать вектор параметров эксперимента из базы данных.
		Читается строка с минимальным id_experiment c отсутствующим time_start
		'''
		try:
			query=	"SELECT * FROM d1_parameters " \
				"WHERE time_start IS NULL " \
				"ORDER BY id_experiment DESC " \
				"LIMIT 1;"
			self.cursor_database.execute(query)
			result = self.cursor_database.fetchone()
			# перезапись кортежа запроса в словарь параметров
			b=0
			for p in self.parameters:
				self.parameters[p]=result[b]
				b=b+1
			print(f"[OK!] read_db_parameters(): The vector of experiment parameters was successfully read from the database. Result:\n {self.parameters}")
			return 1
		except:
			print(f"[FAULT!] read_db_parameters(): Parameter database read error")			
			sys.exit()
				
	def update_parameters(self):
		'''
		Обновить данные о времени проведения эксперимента
		'''
		self.parameters["time_start"]=self.data_series[0][0]
		self.parameters["time_finish"]=self.data_series[-1][1]
		print(f"[OK!] update_parameters(): The vector of experiment parameters was successfully update. Result:\n {self.parameters}")
	
	def update_db_parameters(self):
		'''обновить поле о времени эксперимента в базе данных'''
		query=	"UPDATE d1_parameters " \
				"SET " \
				"time_start = '" + str(self.parameters["time_start"]) + "'," \
				"time_finish = '" + str(self.parameters["time_finish"]) + "' "\
				"WHERE id_experiment = '" + str(self.parameters["id_experiment"]) + "';"
		self.cursor_database.execute(query)
		self.connection_database.commit()
		print(f"[OK!] update_db_parameters(): The vector of experiment parameters was successfully update into datadase.")
		
if __name__=="__main__":
	device_1=Device_1()
	device_1.connect_to_device()
	device_1.get_reading_speed()
	device_1.set_initial_state()
	device_1.connect_to_database()
	device_1.read_db_parameters()
	device_1.push_parameters_to_device()
	device_1.read_data_series()
	device_1.print_data_series()
	device_1.write_db_data_series()
	device_1.update_parameters()
	device_1.update_db_parameters()
	device_1.disconnect_from_database()
	
