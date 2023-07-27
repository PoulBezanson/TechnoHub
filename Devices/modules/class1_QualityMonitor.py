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
import yaml 		#https://habr.com/ru/articles/669684/
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
		
		sys.exit()
	
	def __init__(self):
		'''
		Конструктор
		'''
		self.connections_config_file='./config/connections_config.yaml' # файл сетевой конфигурации
		self.connections_config=None	# структура данных c с параметрами сетевой конфигурации 
		self.experiment_manifest_file='./config/experiment_manifest.yaml' # файл общей конфигурации эксперимента
		self.experiment_manifest=None   # структура данных манифеста эксперимента 
		self.options_manifest_file='./config/options_manifest.yaml' # файл общей конфигурации эксперимента
		self.options_manifest=None      # структура данных манифеста параметров 
		self.results_manifest_file='./config/results_manifest.yaml' # файл общей конфигурации эксперимента
		self.results_manifest=None      # структура данных результатов эксперимента
		self.options_data=None			# структура со значениями данными для проведения эксперимента
		self.device_identifiers=None	# идентификаторы экспериментальной установки
		self.db_config=None				# параметры входа в базу данных
		self.db_connection=None			# коннектор базы данных
		self.bus_config=None			# параметры соединения с промышленной шиной
		self.dv_connection=None			# коннектор промышленной шины
		self.status_device=None    		# текущий статус установки
		self.option_manifest=None    	# структура json со спецификациями эксперимента
		self.fix_claim_id=0				# идентификатор зафиксированной заявки
		self.status_dictionary=None   		# список возможных статусов
		self.init_controller()			# вызов дополнительной процедуры инициализации
		
	
	def init_controller(self):
		'''
		Инициализировать контроллер эксперимента
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
			f'[Controller initialization...]:')
				
		# чтение файла сетевой конфигурации .yaml и идентификация установки
		self.connections_config=self._read_yaml_file(self.connections_config_file)
		self.device_identifiers=self.connections_config['device_identifiers']
				
		# открытие соединения с базой данных сервера
		self.db_config=self.connections_config['db_config']
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
		
		# аутентификация названия установки
		db_cursor=self.db_connection.cursor()
		# TO DO:
		db_cursor.close()
		print('\t','[OK!] Authentication completed')
		
		# формирование словаря режимов контроллера из базы данных список [status_name: id_status]
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
		print(f'\t [OK!] Status dictionary formed:\n'
			  f'\t       {self.status_dictionary}')
		
		# чтение манифестов из базы данных
		self.experiment_manifest=self._pull_one_manifest('experiment_manifest')
		self.options_manifest=self._pull_one_manifest('options_manifest')
		self.results_manifest=self._pull_one_manifest('results_manifest')
				
	def pull_status_device(self, print_message=True):
		'''
		Запросить из базы данных статус установки
		Возвращает: status_name
		'''
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_status_device",[self.device_identifiers['hash_key']])
		_selection = []
		for s in db_cursor.stored_results():
			_selection.append(s.fetchall())
		status_device=_selection[0][0]
		db_cursor.close()
		if print_message==True:
			print(f'\t [ОК!] Pull status: {status_device[0]}\n'
				  f'\t       Тime status: {datetime.utcfromtimestamp(int(status_device[1])).strftime("%Y-%m-%d %H:%M")}.\n' 
				  f'\t       Description: {status_device[2]}')
		return status_device[0]
		
	def pull_options_data(self):
		'''
		Считать с базы данные параметров эксперимента
		'''
		# считывание json объект с базы данных
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_options_data",[self.fix_claim_id])
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		json_data=_response[0][0][0]
		db_cursor.close()
		self.options_data = json.loads(json_data)
		print(f'\t [OK!] Options data was read from database')
		return(self.options_data)
	
	def _pull_amount_notmodification(self):
		'''
		Вернуть количество установок находящихся в любом статусе кроме modification
		Вызывается из push_all_manifest
		'''
		function_parameters=(self.device_identifiers['hash_key'],)
		db_cursor=self.db_connection.cursor()
		function = "SELECT pull_amount_notmodification(%s)"
		result = db_cursor.execute(function, function_parameters)
		amount_notmodification = db_cursor.fetchone()[0]
		return amount_notmodification
				
	def _pull_one_manifest(self, _manifest_name):
		'''
		Считать с базы данных содержимое одного манифеста
		'''
		# считывание json объект манифеста с базы данных
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_one_manifest",[self.device_identifiers['hash_key'], _manifest_name])
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		json_manifest=_response[0][0][0]
		db_cursor.close()
		if '[FALSE!]' in json_manifest:
			print(f'\t {json_manifest}')
			sys.exit()
		else:
			print(f'\t [OK!] Manifest ({_manifest_name}) was read from database')
		# преобразование json в структуру python 
		manifest = json.loads(json_manifest)
		return(manifest)
		
	def push_status_device(self, _status, _description, _db_config):
		'''
		Записать в базу данных статус установки
		'''
		# открытие соединения с базой данных сервера
		db_connection=mysql.connector.connect(
				host=_db_config["host"],
				user=_db_config["user"],
				password=_db_config["password"],
				database=_db_config["database"])
		if db_connection.is_connected():
			db_cursor=db_connection.cursor()
			routin_parameters=[self.device_identifiers['hash_key'],_status,_description]
			db_cursor.callproc("push_status_device",routin_parameters)
			db_connection.commit()
			print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
										f' [Change status...]:                 ')
			print(f'\t [ОК!] Push new status "{_status}" to server with description:\n'
				  f'\t       {_description}')
			db_cursor.close()
			db_connection.close()
			return _status
		else:
			print(f'\t [FAULT!] Lost connection to database')
			sys.exit()
	
	def push_delete_claims(self):
		'''
		Записать в базу данных статус установки
		Возвращает: количество удаленных заявок
		'''
		db_cursor=self.db_connection.cursor()
		routin_parameters=[self.device_identifiers['hash_key']]
		db_cursor.callproc("push_delete_claims",routin_parameters)
		self.db_connection.commit()
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		deleted_claims=_response[0][0][0]
		db_cursor.close()
		print(f'\t [ОК!] Claims deleted in the amount of {deleted_claims} pieces')
		return deleted_claims
	
	def push_unreserve_claims(self):
		'''
		Разрезервировать заявки
		Возвращает: количество разрезервированных заявок
		'''
		db_cursor=self.db_connection.cursor()
		routin_parameters=[self.device_identifiers['hash_key']]
		db_cursor.callproc("push_unreserve_claims",routin_parameters)
		self.db_connection.commit()
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		unreserved_claims=_response[0][0][0]
		db_cursor.close()
		print(f'\t [ОК!] Claims unreserved in the amount of {unreserved_claims} pieces')
		return unreserved_claims
		
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
		
	def get_status_dictionary(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return self.status_dictionary
		
	def get_db_config(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return self.db_config	
	
	def _read_yaml_file(self, _file_name):
		'''
		Прочитать файл в формате .yaml
		'''
		try:
			with open(_file_name, 'r') as file:
				result=yaml.safe_load(file)
				print(f'\t [ОК!] File {_file_name} has been read')
			return result
		except:
			print(f'\t [FAULT!] File {_file_name} has NOT been read')
	
	def _write_yaml_file(self, _file_name, _data):
		'''
		Записать данные файл в формате .yaml
		'''
		try:
			with open(_file_name, 'w') as file:
				yaml.safe_dump(_data,file, sort_keys=False, allow_unicode=True)
				print(f'\t [ОК!] File {_file_name} has been written')
		except:
			print(f'\t [FAULT!] File {_file_name} has NOT been written')
				
	def set_status_device(self, _new_status):
		'''
		Установить новый текущий статус 
		'''
		self.status_device=_new_status
	                                 	
	def push_all_manifests(self):
		'''
		Обновить данные в таблице "experiments" относящиеся к спецификации эксперимента.
		'''
		if self._pull_amount_notmodification()==0:
			
			# чтение файлов манифестов yaml
			self.experiment_manifest=self._read_yaml_file(self.experiment_manifest_file)
			self.options_manifest=self._read_yaml_file(self.options_manifest_file)
			self.results_manifest=self._read_yaml_file(self.results_manifest_file)
			
			# преобразование манифестов в json
			json_experiment_manifest = json.dumps(self.experiment_manifest)
			json_options_manifest = json.dumps(self.options_manifest)
			json_results_manifest = json.dumps(self.results_manifest)
			print(f'\t [ОК!] Data converted to json format')
												
			# подготовка параметров для обновления манифестов в базе данных
			routin_parameters=[]
			routin_parameters.append(self.device_identifiers['hash_key'])
			routin_parameters.append(json_experiment_manifest)
			routin_parameters.append(json_options_manifest)
			routin_parameters.append(json_results_manifest)
					
			# подготовка параметров для обновления производных полей из experiment_manifest
			routin_parameters.append(self.experiment_manifest['name'])
			routin_parameters.append(self.experiment_manifest['experiment_type'])
			routin_parameters.append(self.experiment_manifest['description'])
			routin_parameters.append(self.experiment_manifest['full_description'])
			tags=''
			for tag in 	self.experiment_manifest['tags']:
				for tag in 	self.experiment_manifest['tags']:
					tags=tags+'#'+tag
			routin_parameters.append(tags)
			routin_parameters.append(self.experiment_manifest['owner'])
			routin_parameters.append(self.experiment_manifest['address'])
			routin_parameters.append(self.experiment_manifest['contacts'])
			routin_parameters.append(0) # обновление поля date_update (0 -нет, 1 - да)
			print(f'\t [ОК!] Data for database prepared')
			
			# запись данных в базу данных
			db_cursor=self.db_connection.cursor()
			db_cursor.callproc("push_all_manifests",routin_parameters)
			self.db_connection.commit()
			# обработка ответа базы данных
			_response = []
			for s in db_cursor.stored_results():
				_response.append(s.fetchall())
			db_response=_response[0][0][0]
			db_cursor.close()
			print(f'\t {db_response}')
		else:	
			# обновление файлов манифестов
			self._write_yaml_file(self.experiment_manifest_file, self.experiment_manifest)
			self._write_yaml_file(self.options_manifest_file, self.options_manifest)
			self._write_yaml_file(self.results_manifest_file, self.results_manifest)
			print(f'\t [ОК!] Manifest files updated on local machine')
		
	def push_reserve_claims(self):
		'''
		Зарезервировать пакет заявок для занавесок
		'''
		# формирование списка параметров запроса 
		hash_key=self.device_identifiers['hash_key']
		service_options=self.experiment_manifest['service_options']
		values=service_options['values']
		max_reserved_claims_values=values['max_reserved_claims']
		max_reserved_claims=max_reserved_claims_values['value']
		# запрос на резервирование заявок
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("push_reserve_claims",[hash_key, max_reserved_claims])
		self.db_connection.commit()
		# обработка ответа базы данных
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		reserved_claims=_response[0][0][0]
		db_cursor.close()
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.status_device}]:',end='')
		if reserved_claims!=0:
			print(f' {reserved_claims} claims reserved')
		else:
			print(f' {reserved_claims} claims reserved',end='\r')
		return reserved_claims
		
	def push_fix_claim(self):
		'''
		Фиксировать заявку среди зарезервироанных
		Возвращает id_claim
		'''
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("push_fix_claim",[self.device_identifiers['hash_key']])
		self.db_connection.commit()
		# обработка ответа базы данных
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		db_cursor.close()
		self.fix_claim_id=_response[0][0][0]
		if int(self.fix_claim_id)!=0:
			print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.status_device}]: ',end='')
			print(f' {self.fix_claim_id} id claim fixed')
		return int(self.fix_claim_id)
	
	def push_unfix_claim(self):
		'''
		Фиксировать заявку среди зарезервироанных
		Возвращает id_claim
		'''
		db_cursor=self.db_connection.cursor()
		routin_parameters=[self.device_identifiers['hash_key']]
		db_cursor.callproc("push_unfix_claim",routin_parameters)
		self.db_connection.commit()
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		unfixed_claims=_response[0][0][0]
		db_cursor.close()
		print(f'\t [ОК!] Claims unfixed in the amount of {unfixed_claims} pieces')
		return unfixed_claims
										
	def set_keyboard_value(self,_value):
		'''
		Задать принудительно значение набранное на клавиатуре
		'''
		try:
			self.keyboard_value=_value
			return str(self.keyboard_value)
		except:
			print(f'\t [FAULT!] Error in metod set_keyboard_value()')
			sys.exit()
		
	def set_modbus_connection(self):
		'''
		Инициировать соединение с объектом управления. Оценить скорость чтения вектора выходных данных
		'''
		# открытие соединения с промышленной шиной на основе ранее прочитанных данных connection_config.yaml
		self.bus_config=self.connections_config['modbus_config']
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
			message='NO divice connection by modbus'
			print(f'\t [FAULT!] {message}')
			self.status_device=self.push_status_device('offline', message)
			print(f'\t Stop controller')
			sys.exit() 
		else:
			print('\t','[OK!] Connected to device by modbus')
		
		
	def _get_args_dataset(self, md_reg_name='input'):
		'''
		Сформировать словарь аргументов для команды modbus считывания вектора выходных данных из input регистров 
		'''
		args_dataset_command={}
		# формирование параметров выходных данных - result_manifest.yaml
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		
		# формировние словаря диапазона адресов input регистров 
		# формируется только один диапазон не битовых регистров для считывания
		min_max_registers={'min':65535,'max':0}
		for k, v in values.items():
			if v['mb_reg_type']!='bit' and v['mb_reg_name']==md_reg_name:
				if v['mb_reg_address']<min_max_registers['min']:
					min_max_registers['min']=v['mb_reg_address']
				if v['mb_reg_address']>min_max_registers['max']:
					min_max_registers['max']=v['mb_reg_address']
		print(f'\t [OK!] Created a list of MIN/MAX modbus address registers: {min_max_registers}')
		#!!! нужно предусмотреть проверку правильности инеми регистров
		
		# формирование словаря аргументов modbus функции для группового считывания выходных регистров данных
		function_code = 4
		address=min_max_registers['min']
		number=min_max_registers['max']-min_max_registers['min']+1
		dataset_command_args={'registeraddress': address, 'number_of_registers': number,  'functioncode': function_code}
		print(f'\t [OK!] Created a list of argumentes:\n'
		      f'\t       {dataset_command_args}')
		return dataset_command_args
		
	def get_mb_initial_commands(self):
		'''
		Сформировать словарь параметров modbus команд для считывания вектора начального состояния 
		'''
		mb_initial_commands={}
				
		# формирование значений манифеста параметров модели - options_manifest.yaml
		initial_state=self.options_manifest['initial state']
		values=initial_state['values']
		
		# формирование словаря modbus команд для считывания регистров начального состояния
		initial_mb_commands={}
		for k, v in values.items():
			if v['mb_reg_type']!='bit' and v['mb_reg_name']!=None:
				address_of_holdings=v
				number=registers_dict_max[k]-registers_dict_min[k]+1
				initial_mb_commands[k]={registeraddress: address, number_of_registers: number,  functioncode: fuction_read_codes[k]}
		
		return mb_initial_commands
	
	def up_dataset_vector(self):
		#!!! сделать выполнение команды через try
		'''
		Считать с объекта вектор выходных параметров
		'''	
		# формирование аргументов modbus функции чтения input регистров
		args=self._get_args_dataset(md_reg_name='input')
		address=args['registeraddress']
		number=args['number_of_registers']
		code=args['functioncode']
		# чтение манифеста параметров эксперимента - options_manifest.yaml
		dataset_options=self.options_manifest['time_options']
		values=dataset_options['values']
		delta_time=values['delta_time']['ws_value']
		# формирование выходного вектора
		time_start=dt.datetime.now().timestamp()			
		try:
			dataset_vector=self.dv_connection.read_registers(registeraddress=address,\
															number_of_registers=number,\
															functioncode=code)	
		except:
			message='Dataset vector NOT read by modbus'
			print(f'\t [FAULT!] {message}')
			self.status_device=self.push_status_device('offline', message)
			print(f'\t Stop controller')
			sys.exit()   
		# формирование время опроса вектора
		time_reading=dt.datetime.now().timestamp()-time_start			
		dataset_vector=[time_start]+[time_reading]+dataset_vector
		print(f'\t [OK!] Dataset vector read:\n'
			  f'\t {dataset_vector}')
		# обработке ошибок на основе временных праметров эксперимента
		if time_reading<delta_time:
			description=f'Time_reading={time_reading} (<{delta_time})'
			print(f'\t [OK!] {description}')
		else:
			message=f'Time_reading={time_reading} (>={delta_time}). It is NOT correct'
			print(f'\t [FAULT!] {message}')
			self.status_device=self.push_status_device('offline', message)
			print(f'\t Stop controller')
			sys.exit()      
		return dataset_vector
	
	def __del__(self):
		'''
		Деструктор 
		'''
		print(f'\t [OK!] Stop controller')
	
		
def scan_keyboard(_device, _db_config):
	'''
	Реализует фоновый опрос клавиатуры на предмет ввода режима 
	'''
	# Получаем текущие настройки терминала
	old_settings = termios.tcgetattr(sys.stdin)
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
								_device.push_status_device(chars,'Status set by operator',_db_config)
								_device.status_device=chars
								char1=''
								chars=''
								symbol=1
								update=True
								
					else:
						update=True
				if update==True:
					symbol=2
					
					#return 0
			
		
	finally:
        # Восстанавливаем настройки терминала
		termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
		sys.exit
		
