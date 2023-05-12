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

import minimalmodbus # https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd # https://pandas.pydata.org/pandas-docs/stable/index.html
import time
import datetime as dt
import threading 
import pandas as pd
import numpy as np
import sys
import os
import mysql.connector
import socket
import subprocess
import cv2 # https://docs.opencv.org/4.7.0/
flag_read_data=threading.Event() # флаг управления чтением вектора данных с устройства
flag_read_data_series=threading.Event() # флаг управления чтением временного ряда векторов данных с устройства

class Device_1:
	'''
	Описывет датчик измерения параметров микроклимата
	'''
	def __init__(self):
		'''
		Конструктор
		'''
		# параметры соединения с устройством modbus для connect_to_device()
		self.device_name='d1'
		self.port_name='/dev/ttyUSB0'
		self.slave_address=100
		self.baud_rate=9600
		self.byte_size = 8
		self.stop_bits = 1
		self.time_out=0.1
		self.connection_device=None # экземпляр класса устройства modbus
		self.registeraddress = 0
		self.number_of_registers=7
		self.functioncode=4
		# параметры начальной инициализации устройства для set_initial_state()
		self.init_state =	{"mute_state": 0,
							"unit_state": 1}
		self.ready_state = {"backlight_state":2}
		self.ready_time=10 # предельная длительность инициализации начального состояния (сек.)
		# параметры эксперимента
		self.d_time=1 		# время дискретизации измеряемого процесса (сек.) 
		self.full_time=5 	# длительность эксперимента (сек.)
		self.data_type={'time_start': (np.float64,0),
					'time_reading': (np.float64,0),
					'co2': (np.uint16,0),
					'tvoc':(np.float64,-2),
					'pm1_0':(np.uint16,0),
					'pm2_5':(np.uint16,0),
					'pm10':(np.uint16,0),
					'temperature':(np.float64,-1),
					'humidity':(np.float64,-1)}
		self.parameters={"id_experiment": None,
						 "id_user": None,
						 "publicity": None,
						 "time_start": None,
						 "time_finish": None,
						 "mute_state": None,
						 "unit_state": None}
		self.data_series=[]
		self.data_frame=pd.DataFrame()
		# параметры базы данных
		
		'''
		self.db_config={"host":"192.168.0.113",
						"user":"orangepi",
						"password":"orangepi",
						"database":"technohub"}
		'''
		self.db_config={"host":"192.168.0.110",
						"user":"orangepi",
						"password":"mariadb",
						"database":"technohub"}
		
		
		self.connection_database=None
		# парметры файлов
		self.file_name=None
		self.videofile_extension="mp4" # врасширение видео файла
		self.datafile_extension="csv" # врасширение видео файла
		# парметры вэб-камеры	
		self.temp_videofile_name="captured" # временное имя видео файла
		self.videofile_codec="mp4v"
		self.webcam_fps=23.0
		self.webcam_size=(640, 480)
		self.webcam=None # экземпляр класса вэб камеры
		self.webcam_out=None # экземпляр выходного видео файла
		# параметры соединения с сервером
		self.host_config={"host":"192.168.0.110",
							"user":"administrator",
							"password":"~/.ssh/id_rsa",
							"destination":"/var/www/technohub/EXPERIMENT/TMP/"}
			
	def connect_to_device(self):
		'''
		Инициализировать связь с устройством. 
		'''
		try:
			self.connection_device = minimalmodbus.Instrument(self.port_name, self.slave_address)  # port name, slave address (in decimal)
			self.connection_device.serial.baudrate = self.baud_rate
			self.connection_device.serial.bytesize = self.byte_size
			self.connection_device.serial.stopbits = self.stop_bits
			self.connection_device.serial.timeout  = self.time_out          # seconds
			self.connection_device.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
			self.connection_device.clear_buffers_before_each_transaction = True
		except:
			print("[FAULT!] connect_to_device(): Sensor connection error")
			return 1
		else:
			print("[OK!] connect_to_device(): Successful connection with the device")
			return self.connection_device
	
	def get_reading_speed(self):
		'''
		Тестировать скорость считывания данных устройства
		Возвращает время разового опроса одного вектора параметров устройства.
		'''
		flag_read_data.set()
		self.__read_data()
		flag_read_data.clear()
		time_reading=self.data_series[0][1]
		print(f"[OK!] get_reading_speed(): The sensor polling time was (seconds) - {time_reading:.6f}")
		self.data_series.pop()
		return time_reading
	
	def set_initial_state(self):
		'''
		Привести объект в начальное состояние и контролировать приведение.
		Параметры для приведения опредеяются вектором init_state.
		Время приведения ограничено значением self.time_init.
		'''
		# преобразование mute_state и unit_state в битовое поле 
		reg17_state=self.init_state["mute_state"] | (self.init_state["unit_state"]<<1)
		#self.connection_device.write_register(registeraddress=16, value=init_state["backlight"], number_of_decimals=0, functioncode=6)
		self.connection_device.write_register(registeraddress=17, value=reg17_state, number_of_decimals=0, functioncode=6)
		# контроль приведения в начальное состояние
		flag_init=0
		t=0
		print("[...] set_initial_state(): Waiting for initial state initialization")
		while (t < self.ready_time) and (flag_init==0):
			backlight=self.connection_device.read_register(registeraddress=16, number_of_decimals=0, functioncode=3)
			if backlight==self.ready_state["backlight_state"]:
				print(f"[ОК!] set_initial_state(): Device initialization done")
				flag_init=1
				return 0
			time.sleep(1)
			t=t+1
		print(f"[FAULT!] set_initial_state(): Device initialization problem")
		return 1
	
	def __read_data(self):
		'''
		Читать вектор данных из устройства.
		'''
		flag_read_data.wait()
		time_start=dt.datetime.now().timestamp()
		'''
		co2=self.connection_device.read_register(registeraddress=0, number_of_decimals=0, functioncode=4)  # Registernumber, number of decimals
		tvoc=self.connection_device.read_register(registeraddress=1, number_of_decimals=2, functioncode=4)
		pm1_0=self.connection_device.read_register(registeraddress=2, number_of_decimals=0, functioncode=4)
		pm2_5=self.connection_device.read_register(registeraddress=3, number_of_decimals=0, functioncode=4)
		pm10=self.connection_device.read_register(registeraddress=4, number_of_decimals=0, functioncode=4)
		temperature=self.connection_device.read_register(registeraddress=5, number_of_decimals=1, functioncode=4)
		humidity=self.connection_device.read_register(registeraddress=6, number_of_decimals=1, functioncode=4)
		time_reading=dt.datetime.now().timestamp()-time_start
		self.data_series.append([time_start, time_reading, co2, tvoc, pm1_0, pm2_5, pm10, temperature, humidity])
		'''
		_data_series=self.connection_device.read_registers(self.registeraddress, self.number_of_registers, self.functioncode)  # Registernumber, number of decimals
		#tsk2-1
		time_reading=dt.datetime.now().timestamp()-time_start
		self.data_series.append([time_start, time_reading]+ _data_series)
				
		flag_read_data.clear()
	
	def read_data_series(self):
		'''
		Читать временной ряд данных из устройства и записывать видео файл.
		'''
		# запуск видео записи
		read_webcam_tread=threading.Thread(name='read_webcam_thread',target=self.__read_webcam)
		read_webcam_tread.start()
		flag_read_data_series.set()
		# запуск записи данных
		print("[...] read_data_series(): Data series reading")
		t=0
		while t<self.full_time:
			read_data_thread=threading.Thread(name='read_data_thread',target=self.__read_data)
			holdup_time_thread=threading.Thread(name='holdup_time_thread',target=self.__holdup_time)
			read_data_thread.start()
			holdup_time_thread.start()
			holdup_time_thread.join()
			t=t+self.d_time
		#Обновление данных о времени проведения эксперимента.
		self.parameters["time_start"]=self.data_series[0][0]
		self.parameters["time_finish"]=self.data_series[-1][0]
		#формирование нового имени видео файла
		if len(str(self.parameters["time_start"]))==17:
			self.file_name=self.device_name+'_'+str(self.parameters["time_start"])
		elif len(str(self.parameters["time_start"]))==16:
			self.file_name=self.device_name+'_'+str(self.parameters["time_start"])+'0'
		else:
			print("[FAULT!] clear_data_series(): Video file name formation error")
			sys.exit()	
		flag_read_data_series.clear()
		print(f"[ОК!] read_data_series(): Data series read successfully: dTime={self.d_time}, FullTime={self.full_time}")
		return 0

	def processing_data_series(self):
		'''
		Обработать данные временного ряд векторов.
		
		'''
		print("[...] processing_data_series()") #, end='\r')
		# формирование названия колонок
		columns_name=[x for x in self.data_type]
		# формирование таблицы DataFrame из временного ряда векторов параметров
		temp_df = pd.DataFrame(self.data_series,columns=columns_name)
		self.data_frame  = pd.concat([self.data_frame,temp_df])
		# коррекция типа данных таблицы
		self.data_frame=self.data_frame.astype({x:self.data_type[x][0] for x in self.data_type})
		# преобразование данных - сдвиг запятой
		for x in self.data_type:
			self.data_frame[x]=self.data_frame[x]*pow(10,int(self.data_type[x][1]))
		# запись данных в файл 
		datafile_name=self.file_name+'.'+self.datafile_extension		
		self.data_frame.to_csv(datafile_name)
		print("[...] processing_data_series(): Print data series:\n")
		print(self.data_frame)
		return 0
	
	def __holdup_time(self):
		'''
		Удержать время на единицу дискретизации d_time.
		'''
		flag_read_data.set()
		time.sleep(self.d_time)
			
	def clear_data_series(self):
		'''
		Отчистить значения атрибута вектора временного ряда.
		'''
		self.data_series=[]
		print("[ОК!] clear_data_series(): Data series cleared")
		return 0
	
	def print_data_series(self):
		'''
		Напечатать значения временного ряда.
		'''
		print("[ОК!] print_data_series(): Data series:")
		for v in self.data_series:
			print(v)
		
	def connect_to_database(self):
		'''
		Инициализировать соединение с базой данных
		'''
		try:
			self.connection_database=mysql.connector.connect(
				host=self.db_config["host"],
				user=self.db_config["user"],
				password=self.db_config["password"],
				database=self.db_config["database"])
			if self.connection_database.is_connected():
				print("[OK!] connect_to_database(): Connected to MySQL database")
				return self.connection_database
		except:
			print("[FAULT!] connect_to_database(): Data Base connection error")
			sys.exit()
	
	def disconnect_from_database(self):
		'''
		Разорвать соединение с базой данных.
		'''
		if self.connection_database.is_connected():
			self.connection_database.close()
			print("[OK!] disconnect_from_database(): MySQL connection is closed")
	
	def write_db_data_series(self):
		'''
		Записать временной ряд данных в базу данных.
		'''
		cursor_database=self.connection_database.cursor()
		s=""
		for p in self.data_type:
			s=s + "%s, "
		s=s[:-2]
		query="call " + self.device_name + "_write_db_series(" + s + ");"
		cursor_database.executemany(query, self.data_series)
		self.connection_database.commit()
		cursor_database.close()
		self.data_series=[]
		print("[OK!] write_db_data_series(): Record inserted successfully into database table")  

	def push_parameters_to_device(self):
		'''отправить вектор параметров экспериментана на устройство'''
		reg17_state=self.parameters["mute_state"] | (self.parameters["unit_state"]<<1)
		self.connection_device.write_register(registeraddress=17, value=reg17_state, number_of_decimals=0, functioncode=6)
		print("[ОК!] push_parameters_to_device(): Parameter vector sent to device")
		return 0
		
	def read_db_parameters(self):
		'''
		Читать вектор параметров эксперимента из базы данных.
		Читается строка с минимальным id_experiment c отсутствующим time_start
		'''
		# чтение списка колонок таблицы параметров эксперимента
		column_name = []
		cursor_database=self.connection_database.cursor()
		cursor_database.callproc("read_db_columns",[self.device_name])
		# tsk1-1 приведение списка колонок в удобному виду - избавление от вложенностей 
		stored_results=cursor_database.stored_results()
		for r in stored_results:
			_column_name = r.fetchall()
		for r in _column_name:
			column_name.append(r[0])
		# считывание из БД значений параметров эксперимента
		parameters_select=None
		cursor_database.callproc("read_db_parameters",[self.device_name])
		_parameters_select = []	
		for r in cursor_database.stored_results():
			_parameters_select.append(r.fetchall())
		cursor_database.close()
		try:
			parameters_select=_parameters_select[0][0]
		except IndexError:
			parameters_select=None
		if parameters_select!=None:
			# перезапись кортежа запроса в словарь параметров
			if len(column_name)==len(self.parameters):
				b=0
				for p in column_name:
					self.parameters[p]=parameters_select[b]
					b=b+1
				print(f"[OK!] read_db_parameters(): The vector of experiment parameters was successfully read from the database. Result:\n {self.parameters}")
				return 0
			else:
				print(f"[FAULT!] read_db_parameters(): Parameter mismatch")
				sys.exit()
			#print(self.parameters)
		else:
			print("[FAULT!] read_db_parameters(): Parameter list is None")
			return 1	
						
	def update_db_parameters(self):
		'''
		Обновить поле о времени эксперимента в базе данных.
		'''
		#tsk1-2
		cursor_database=self.connection_database.cursor()
		cursor_database.callproc("update_db_parameters",[self.device_name,self.parameters["id_experiment"],self.parameters["time_start"],self.parameters["time_finish"]])
		self.connection_database.commit()
		cursor_database.close()
		print(f"[OK!] update_db_parameters(): The vector of experiment parameters was successfully update into datadase.")
	
	def initialize_webcam(self):
		'''
		Вполнить захват и инициализацию вэб камеры
		'''
		self.webcam = cv2.VideoCapture(1)
		#Error if capture failed
		if not self.webcam.isOpened():
			print("[FAULT!] make_camera_capture(): Can`t capture the webcam")
			return 1
		webcam_codec=cv2.VideoWriter_fourcc(*self.videofile_codec)
		temp_videofile_name=self.temp_videofile_name + '.' + self.videofile_extension
		self.webcam_out=cv2.VideoWriter(temp_videofile_name, webcam_codec, self.webcam_fps, self.webcam_size)
		print("[OK!] initialize_webcam(): Camera capture completed successfully")
		return 0
	
	def __read_webcam(self):
		flag_read_data_series.wait()
		while(flag_read_data_series.is_set()):
			ret, frame = self.webcam.read()
			if ret:
				self.webcam_out.write(frame)
			else:
				print("[FAULT!] read_webcam(): Can`t receive frame")
				return 0
		#Closing file and camera lock
		self.webcam.release()
		self.webcam_out.release()
		# Переименовываем файл
		videofile_name=self.file_name+'.'+self.videofile_extension
		temp_videofile_name=self.temp_videofile_name+'.'+self.videofile_extension
		if os.path.exists(temp_videofile_name):
			os.rename(temp_videofile_name, videofile_name)
			print(f"[OK!] _read_webcam(): The webcam has successfully completed the video recording. Video file: {self.file_name}")
			return videofile_name
		else:
			print(f"[FAULT!] read_webcam(): Video file {videofile_name} not exist")
			return 1
	def push_server_files(self):
		'''
		Отправляет видео файл на сервер и удаляет его на источнике
		'''
		# передача  файла на сервер
		print("[...] push_server_file():")
		videofile_name=self.file_name+'.'+self.videofile_extension
		datafile_name=self.file_name+'.'+self.datafile_extension
		file_names=[videofile_name, datafile_name]
		for file_name in file_names:
			print("[...] push_server_file(): Waiting for the file to be generated")
			while not os.path.exists(file_name):
				pass
			rsync_command = f"rsync -avz -e ssh {file_name} {self.host_config['user']}@{self.host_config['host']}:{self.host_config['destination']}"
			subprocess.run(rsync_command, shell=True)
			print(f"[ОК!] push_server_file(): The file {file_name} was successfully sent to the server")
			# удаление файла из текущей папки
			os.remove(file_name)
			if not os.path.exists(file_name):
				print("[ОК!] push_server_file(): File deleted successfully")
				
			else:
				print("[FAULT!] push_server_file(): Problem deleting a file in a folder")
				#sys.exit()
				return 1
		return 0
		
if __name__=="__main__":
	device_1=Device_1()
	device_1.connect_to_database()
	while 1:
		while not device_1.read_db_parameters():
			device_1.connect_to_device()
			device_1.get_reading_speed()
			if device_1.set_initial_state():
				break
			device_1.push_parameters_to_device()
			device_1.initialize_webcam()
			device_1.read_data_series()
			device_1.processing_data_series()
			device_1.print_data_series()
			device_1.write_db_data_series()
			device_1.update_db_parameters()
			device_1.push_server_files()
		device_1.disconnect_from_database()
		print(f"[...] read_db_parameters(): Waiting for the experiment")
		time.sleep(5)
		device_1.connect_to_database()
	
