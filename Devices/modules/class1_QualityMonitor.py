#/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
# -----------------------------------------------------
# The program generates a time series of atmospheric parameter 
# vectors read from the sensor, which is connected to the 
# microcontroller via the modbus bus.
# file name: OpcServer.py
# virtual environment: envDevices
# author: Poul Bezanson
# email:

import minimalmodbus # https://minimalmodbus.readthedocs.io/en/master/index.html
import pandas as pd # https://pandas.pydata.org/pandas-docs/stable/index.html
import yaml
import json
import time
import datetime as dt
from datetime import datetime
import threading 
import termios
import tty
import pandas as pd
import numpy as np
import sys
import os
import mysql.connector
import socket
import subprocess
import cv2 # https://docs.opencv.org/4.7.0/

class Device:
	'''
	Описывет датчик измерения параметров микроклимата	
	'''
	
	def test(self):
		# запись данных в базу данных
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("push_manifests_",[])
		self.db_connection.commit()
		# обработка ответа базы данных
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		response=_response[0][0][0]
		db_cursor.close()
		#response=response.strip()
		string_r='[ОК!] Data written to the database'
		string_m='[OK!] Data written to the database'
		print(f'String_r={string_r}')
		print(f'String_m={string_m}')
		print(f'Responce={response}')
		if 'OK!' in response:
			print("Блять!!!")
		
		for i in range(0,len(response)):
			if response[i:i+1]==string_m[i:i+1]:
				print(string_r[i:i+1], end='')
		sys.exit()
	
	def __init__(self):
		'''
		Конструктор
		'''
		self.connections_config_file='./config/connections_config.yaml' # файл сетевой конфигурации
		self.experiment_manifest_file='./config/experiment_manifest.yaml' # файл общей конфигурации эксперимента
		self.options_manifest_file='./config/options_manifest.yaml' # файл общей конфигурации эксперимента
		self.results_manifest_file='./config/results_manifest.yaml' # файл общей конфигурации эксперимента
		self.device_identifiers=None	# идентификаторы экспериментальной установки
		self.db_config=None				# параметры входа в базу данных
		self.db_connection=None			# коннектор базы данных
		self.bus_config=None			# параметры соединения с промышленной шиной
		self.dv_connection=None			# коннектор промышленной шины
		self.status_device=[]    		# текущий статус установки
		self.previus_status=[] 			# предыдущий статус канала
		self.keyboard_value='None'		# последнее набранное значение на клавиатуре
		self.option_manifest=None    	# структура json со спецификациями эксперимента
		
		self.status_dictionary=None   		# список возможных статусов
		self.init_controller()			# вызов дополнительной процедуры инициализации
	
	def init_controller(self):
		'''
		Инициализировать контроллер эксперимента
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.init_controller.__name__}]:')
		
		# чтение файла сетевой конфигурации .yaml и идентификация установки
		connections_config=self.read_connections_config()
		self.device_identifiers=connections_config['device_identifiers']
		
		# открытие соединения с базой данных сервера
		self.db_config=connections_config['db_config']
		self.db_connection=mysql.connector.connect(
				host=self.db_config["host"],
				user=self.db_config["user"],
				password=self.db_config["password"],
				database=self.db_config["database"])
		if self.db_connection.is_connected():
			print('\t','[OK!] Connected to database')
		else:
			print('\t','[FAULT!] No database connection')
			sys.exit()
		
		# формирование из базы данных список режимов контроллера
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_status_list",[])
		_selection = []
		for s in db_cursor.stored_results():
			_selection.append(s.fetchall())
		_selection=_selection[0]
		db_cursor.close()
		self.status_dictionary={}
		for s in _selection:
			self.status_dictionary[s[0]]=s[1]
					
		# Аутентификация названия установки
		db_cursor=self.db_connection.cursor()
		# TO DO:
		db_cursor.close()
		print('\t','[OK!] Authentication completed')
		
		
	def pull_status_device(self):
		'''
		Запросить из базы данных статус установки 
		'''
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_status_device",[self.device_identifiers['hash_key']])
		_selection = []
		for s in db_cursor.stored_results():
			_selection.append(s.fetchall())
		status_device=_selection[0][0]
		db_cursor.close()
		print(f'\t [ОК!] Pull status: {status_device[0]}\n'
		      f'\t       Тime status: {datetime.utcfromtimestamp(int(status_device[1])).strftime("%Y-%m-%d %H:%M")}.\n' 
		      f'\t       Description: {status_device[2]}')
		return status_device
		
	def push_status_device(self, _description, _status):
		'''
		Записать в базу данных статус установки
		'''
		db_cursor=self.db_connection.cursor()
		routin_parameters=[self.device_identifiers['hash_key'],_status,_description]
		db_cursor.callproc("push_status_device",routin_parameters)
		self.db_connection.commit()
		print(f'\t [ОК!] New status with description sent to database.')
		db_cursor.close()
		return 0
	
	def push_delete_claims(self):
		'''
		Записать в базу данных статус установки
		'''
		db_cursor=self.db_connection.cursor()
		routin_parameters=[self.device_identifiers['hash_key']]
		db_cursor.callproc("push_delete_claims",routin_parameters)
		self.db_connection.commit()
		print(f'\t [ОК!] New status with description sent to database.')
		db_cursor.close()
		return 0
		
	def get_status_id(self,_status_name):
		'''
		Возвращает id кодировку названия статуса
		'''
		return self.status_dictionary[_status_name]
	
	def get_status_device(self):
		'''
		Получить текущий статус контроллера
		'''
		return self.status_device
		
	def get_previus_status(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return self.previus_status
		
	def get_keyboard_value(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return str(self.keyboard_value)
	
	def get_status_dictionary(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return self.status_dictionary
	
	def read_connections_config(self):
		'''
		Прочитать файл с параметрами соединений 
		'''
		try:
			with open(self.connections_config_file, 'r') as file:
				result=yaml.safe_load(file)
				print('\t','[ОК!] Connection config file read')
			return result
		except:
			print('\t','[FAULT!] Connection config file NOT read')
			
	def read_experiment_manifest(self):
		'''
		Прочитать файл с параметрами эксперимента 
		'''
		try:
			with open(self.experiment_manifest_file, 'r') as file:
				result=yaml.safe_load(file)
				print('\t','[ОК!] Experiment_manifest file read')
			return result
		except:
			print('\t','[FAULT!] Experiment_manifest file NOT read')
	
	def read_options_manifest(self):
		'''
		Прочитать файл с параметрами модели 
		'''
		try:
			with open(self.options_manifest_file, 'r') as file:
				result=yaml.safe_load(file)
				print('\t','[ОК!] Options manifest file read')
			return result
		except:
			print('\t','[FAULT!] Options manifest file NOT read')
	
	def read_results_manifest(self):
		'''
		Прочитать файл с параметрами разультирующего вектора 
		'''
		try:
			with open(self.results_manifest_file, 'r') as file:
				result = yaml.safe_load(file)
				print('\t','[ОК!] Results manifest file read')
			return result
		except:
			print('\t','[FAULT!] Results manifest file NOT read')
		
	def set_status_device(self, _new_status):
		'''
		Установить новый текущий статус 
		'''
		self.status_device=_new_status
	
	def set_previus_status(self,_new_status):
		'''
		Установить новый текущий статус 
		'''
		self.previus_status=_new_status
							                                 	
	def push_manifests(self):
		'''
		Обновить данные в таблице "experiments" относящиеся к спецификации эксперимента.
		'''
		# чтение файла манифеста эксперимента
		
		# !!! нужно добавить try 
		
		# чтение файла манифеста параметров модели
		experiment_manifest=self.read_experiment_manifest()
				
		# чтение файла манифеста параметров модели
		options_manifest=self.read_options_manifest()
				
		# чтение атрибутов манифеста выходных данных
		results_manifest=self.read_results_manifest()
					
		# подготовка данных манифестов для обновления
		if experiment_manifest['time_update']==options_manifest['time_update'] and \
			experiment_manifest['time_update']==results_manifest['time_update']:
			routin_parameters=[]
			routin_parameters.append(experiment_manifest['time_update'])
			routin_parameters.append(self.device_identifiers['hash_key'])
			routin_parameters.append(experiment_manifest['name'])
			routin_parameters.append(experiment_manifest['experiment_type'])
			routin_parameters.append(experiment_manifest['description'])
			routin_parameters.append(experiment_manifest['full_description'])
			del options_manifest['time_update']
			json_options_manifest = json.dumps(options_manifest)
			routin_parameters.append(json_options_manifest)
			del results_manifest['time_update']
			json_results_manifest = json.dumps(results_manifest)
			routin_parameters.append(json_results_manifest)
			tags=''
			for tag in 	experiment_manifest['tags']:
				tags=tags+'#'+tag
			routin_parameters.append(tags)
			routin_parameters.append(experiment_manifest['owner'])
			routin_parameters.append(experiment_manifest['address'])
			routin_parameters.append(experiment_manifest['contacts'])
			print('\t','[ОК!] Data for database prepared')	
			#!!!!!!!!!!!!!!!!!!!!!!!!!!!
			# запись данных в базу данных
			db_cursor=self.db_connection.cursor()
			db_cursor.callproc("push_manifests",routin_parameters)
			self.db_connection.commit()
			# обработка ответа базы данных
			_response = []
			for s in db_cursor.stored_results():
				_response.append(s.fetchall())
			db_response=_response[0][0][0]
			db_cursor.close()
			print(f'\t {db_response}')
			if 'OK!' in db_response:
				return 0
			else:
				sys.exit()
		else:
			print(f'\t [FAULT!] Times in manifest files are NOT equivalent')
			print(f'\t [FAULT!] Status NOT updated')
			print(f'\t [FAULT!] STOP controller on stage 1')
			sys.exit()
				
	def up_init_connection(self):
		'''
		Инициировать соединение с объектом управления. Оценить скорость чтения вектора выходных данных  
		'''
		# открытие соединения с промышленной шиной
		connections_config=self.read_connections_config()
		self.bus_config=connections_config['modbus_config']
		try:
			self.dv_connection=minimalmodbus.Instrument(self.bus_config['port_name'],\
															  self.bus_config['slave_address'])  # port name, slave address (in decimal)
			self.dv_connection.serial.baudrate = self.bus_config['baud_rate']
			self.dv_connection.serial.bytesize = self.bus_config['byte_size']
			self.dv_connection.serial.stopbits = self.bus_config['stop_bits']
			self.dv_connection.serial.timeout  = self.bus_config['time_out']
			self.dv_connection.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
			self.dv_connection.clear_buffers_before_each_transaction = True
		except:
			print('\t','[FAULT!] NO divice connection by modbus')
			sys.exit() 
		else:
			print('\t','[OK!] Connected to device by modbus')
		
		# чтение манифеста параметров выходных данных 
		results_manifest=self.read_results_manifest()
		dataset_options=results_manifest['dataset_options']
		values=dataset_options['values']
		
		# формировние словаря имен регистров указанием самого младшего адреса  
		registers_dict_min={}
		for k, v in values.items():
			if v['mb_reg_name']!=None and not (v['mb_reg_name'] in registers_dict_min):
				registers_dict_min[v['mb_reg_name']]=v['mb_reg_address']
			elif v['mb_reg_name']!=None and v['mb_reg_address']<registers_dict_min[v['mb_reg_name']]:
				registers_dict[v['mb_reg_name']]=v['mb_reg_address']
		print(f'\t [OK!] Created a list of registers: {registers_dict_min}')
		#!!! нужно предусмотреть проверку правильности инеми регистров
		
		# формировние словаря имен регистров указанием самого старшего адреса  
		registers_dict_max={}
		for k, v in values.items():
			if v['mb_reg_name']!=None and not (v['mb_reg_name'] in registers_dict_max):
				registers_dict_max[v['mb_reg_name']]=v['mb_reg_address']
			elif v['mb_reg_name']!=None and v['mb_reg_address']>registers_dict_max[v['mb_reg_name']]:
				registers_dict_max[v['mb_reg_name']]=v['mb_reg_address']
		print(f'\t [OK!] Created a list of registers: {registers_dict_max}')
		#!!! нужно предусмотреть проверку правильности инеми регистров
		
		# формирование команд 
		dataset_vector=[]
		for k, v in registers_dict_min.items():
			register_address=v
			number_of_registers=registers_dict_max[k]-registers_dict_min[k]+1
			if k=='input':
				function_code=4
			if k=='holding':
				function_code=3
			dataset_vector=dataset_vector+self.dv_connection.read_registers(register_address,\
											number_of_registers,\
											function_code)
		print(f'\t [OK!] Dataset vector read: {dataset_vector}')
		return 0
		
def scan_keyboard(_device):
	'''
	Реализует фоновый опрос клавиатуры на предмет ввода режима 
	'''
	# Получаем текущие настройки терминала
	old_settings = termios.tcgetattr(sys.stdin)
	# выводим на экран список доступных режимов
	print('\t Enter key: ',end='')
	print(f'{_device.get_status_dictionary().keys()}')
	
	try:
		# Устанавливаем необработанный (raw) режим терминала
		tty.setcbreak(sys.stdin.fileno())
		char1=''
		symbol=1
		while True:
			chars=char1
			update=False
			while update==False:
				char1=sys.stdin.read(1)
				chars = chars + char1	
				print(f'\t              ',end='\r')
				print(f'\t {chars}*',end='\r')
				for x in _device.get_status_dictionary().keys():
					#print(x)
					if chars[:symbol]==x[:symbol]:
						if symbol<len(x):
							symbol=symbol+1
							update=False
							break
						else:
							if symbol==len(x):
								_device.keyboard_value=chars
								print(f'\t [OK!] New status: {_device.keyboard_value}!!!')
								char1=''
								symbol=1
								update=True
								break
					else:
						update=True
				if update==True:
					symbol=2
	finally:
        # Восстанавливаем настройки терминала
		termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
		sys.exit

