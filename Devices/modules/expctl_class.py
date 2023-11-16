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
import shutil

# шина событий
event_up_vector=threading.Event() # флаг управления чтением вектора данных с устройства
event_start_experiment=threading.Event() # флаг начала эксперимента

class Device:
	'''
	Описывет датчик измерения параметров микроклимата	
	'''
	
	def test(self):
		self.up_initional_flag()
		sys.exit()
	
	def __init__(self):
		'''
		Конструктор
		'''
		self.bus_config=None			# параметры соединения с промышленной шиной
		self.config_folder='./1_config_aqm'
		self.connections_config_file='connections_config.yaml' # файл сетевой конфигурации
		self.connections_config=None	# структура данных c с параметрами сетевой конфигурации 
		self.dataset=[]					# выходной набор данных
		self.delta_time=0				# время дискретизация выходных данных эксперимента
		self.device_identifiers=None	# идентификаторы экспериментальной установки
		self.db_config=None				# параметры входа в базу данных
		self.db_connection=None			# коннектор базы данных
		self.dv_connection=None			# коннектор промышленной шины
		self.duration_time=0			# длительность отдельного эксперимента
		self.experiment_manifest_file='experiment_manifest.yaml' # файл общей конфигурации эксперимента
		self.experiment_manifest=None   # структура данных манифеста эксперимента 
		self.fix_claim_id=0				# идентификатор зафиксированной заявки
		self.mb_args_dataset={}			# словарь аргументов для modbus команды считывания группы регистров
		self.offline_message=None		# сообщение передаваемое при нештатном выходе в offline
		self.options_data=None			# структура со значениями данными для проведения эксперимента
		self.options_manifest_file='options_manifest.yaml' # файл общей конфигурации эксперимента
		self.options_manifest=None      # структура данных манифеста параметров 
		self.option_manifest=None    	# структура json со спецификациями эксперимента
		self.output_files={}			# словарь выходных файлов для отправки на сервер
		self.results_manifest_file='results_manifest.yaml' # файл общей конфигурации эксперимента
		self.results_manifest=None      # структура данных результатов эксперимента
		self.status_device=None			# текущий статус установки
		self.status_dictionary=None		# список возможных статусов
		self.temp_output_files={}		# словарь временных выходных файлов
		self.thread_read_videocam=None	# поток записи видео
		self.thread_delta_timer=None	# поток таймера дискретизации
		self.videocam=None				# экземпляр класса видеокамеры
		self.videocam_out=None			# экземпляр класса выходного видео файла
		
		# действия инициализации контроллера
		self.init_controller()			# вызов дополнительной процедуры инициализации
			
	def init_controller(self):
		'''
		Инициализировать контроллер эксперимента
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
			f'[Controller initialization...]:')
		
		# формирование полных путей конфигурационных файлов
		self.connections_config_file=self.config_folder+'/'+self.connections_config_file
		self.experiment_manifest_file=self.config_folder+'/'+self.experiment_manifest_file
		self.options_manifest_file=self.config_folder+'/'+self.options_manifest_file
		self.results_manifest_file=self.config_folder+'/'+self.results_manifest_file
		
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
			print('\t','[CRASH!] No database connection')
			sys.exit()
		
		# аутентификация названия установки
		db_cursor=self.db_connection.cursor()
		# TODO:
		#
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
		Возвращает: status_name / 0 
		'''
		#!!! зависает при обрыве соединения
		try:	
			db_cursor=self.db_connection.cursor()
			db_cursor.callproc("pull_status_device",[self.device_identifiers['hash_key']])
		except:
			print(f'\t [FAULT!] Device status is NOT pulled')
			return 0
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
	
	def processing_dataset(self):
		'''
		Обработать наборы данных. Сформировать выходные файлы
		Возвращает: 0 /
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.status_device}]: ',end=' ')
		print(f'Data set processing...')
		# подготовка параметров временного видео файла
		video_options=self.results_manifest['video_options']
		values=video_options['values']
		extension=values['extension']
		temp_videofile_name=extension['temp_name']
		videofile_extension=extension['value']
		temp_videofile_name=temp_videofile_name+'.'+videofile_extension
		videofile_suffix=extension['suffix']
		self.temp_output_files[videofile_suffix]=temp_videofile_name # добавление имени файла в словарь
		
		# подготовка параметров целевого видео файла
		videofile_name=self.fix_claim_id + '_' + videofile_suffix + '.' + videofile_extension
		self.output_files[videofile_suffix]=videofile_name # добавление имени файла в словарь
				
		# подготовка параметров временного файла данных
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		extension=values['extension']
		temp_datafile_name=extension['temp_name']
		datafile_extension=extension['value']
		temp_datafile_name=temp_datafile_name+'.'+datafile_extension
		datafile_suffix=extension['suffix']
		self.temp_output_files[datafile_suffix]=temp_datafile_name # добавление имени файла в словарь
		
		# подготовка параметров целевого файла данных
		datafile_name=self.fix_claim_id + '_' + datafile_suffix + '.' + datafile_extension
		self.output_files[datafile_suffix]=datafile_name # добавление имени файла в словарь
		print(f"\t Parameters of temporary and target files are formed")
		
		# формирование названия полей таблицы данных
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		columns_name=[]
		for key, value in values.items():
			columns_name.append(value['ws_value'])
		columns_name.pop(0) # удаление из списка значений: extension
		print(f"\t [OK!] Created column_names:\n {columns_name}")
		
		# формирование таблицы DataFrame из списка данных
		dataframe=pd.DataFrame(self.dataset,columns=columns_name)
		print(f"\t [OK!] DataFrame table formed")
		
		# преобразование типов данных для dataframe
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		columns_type={}
		for name in columns_name:
			if values[name]['mb_reg_type']=='uint16_t':
				columns_type[name]=np.uint16
			if values[name]['mb_reg_type']=='int16_t':
				columns_type[name]=np.int16
		dataframe=dataframe.astype(columns_type)	
		columns_type={}
		for name in columns_name:
			if values[name]['mb_decimals']>0:
				columns_type[name]=np.float64
		dataframe=dataframe.astype(columns_type)	
		print(f"\t [OK!] DataFrame table type conversion done")
		
		# формирование величины округления и сдвига запятой десятичной части в dataframe
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		columns_decimal={}
		for name in columns_name:
			columns_decimal[name]=values[name]['mb_decimals']
		print(f"\t [OK!] Comma shift defined for dataframe:\n {columns_decimal}")
		
		# сдвиг десятичной запятой и округление
		for name in columns_name:
			if  values[name]['mb_reg_type']!=None: # что соответствует !='null' в .yaml
				dataframe[name]=dataframe[name]*pow(10,-columns_decimal[name])
		dataframe=dataframe.round(columns_decimal)
		print(f"\t [OK!] Dataset shift and rounding done")
				
		# запись данных во временный файл
		separator=';' # разделитель данных в выходном файле
		decimal=','   # разделитель дробной чати в выходном файле
		dataframe.to_csv(path_or_buf=temp_datafile_name, sep=separator, decimal=decimal)
		print(f"\t [OK!] The dataset is written to a temporary file : {temp_datafile_name}")
				
		# операции копирования и удаления над файлами
		for key, item in self.output_files.items():
			file_name=self.output_files[key]
			temp_file_name=self.temp_output_files[key]
			if os.path.exists(temp_file_name):
				shutil.copyfile(temp_file_name, file_name)
				#os.remove(temp_videofile_name)
				print(f"\t [OK!] Created file {file_name}")
			else:
				self.offline_message=f'File {file_name} not exist'
				print(f" \t [CRASH!] {self.offline_message}")
				return 1
		print(f"\t [OK!] File copy and delete operations completed")
		return 0		
	
	def pull_options_data(self):
		'''
		Считать с базы данные параметров эксперимента
		'''
		# считывание json объект с базы данных
		self.options_data=None
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_options_data",[self.fix_claim_id])
		_response = []
		for s in db_cursor.stored_results():
			_response.append(s.fetchall())
		json_data=_response[0][0][0]
		db_cursor.close()
		self.options_data = json.loads(json_data)
		print(f'\t [OK!] Options data was read from database')
		return 0
	
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
		if '[CRASH!]' in json_manifest:
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
			print(f'\t [CRASH!] Lost connection to database')
			sys.exit()
	
	def push_data_files(self):
		'''
		Подготовить и отправить файлы с наборами данных на сервер
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.status_device}]: ',end=' ')
		print(f'Sending data files to the server...')
		# формирование параметров связи с файл-сервером
		fileserver_config=self.connections_config['fileserver_config']
		user=fileserver_config['user']
		host=fileserver_config['host']
		folder=fileserver_config['folder']
		# передача  файла на сервер
		for key, item in self.output_files.items():
			file_name=self.output_files[key]
			counter=5 # максимальное время ожидания файла в папке
			while not os.path.exists(file_name) and counter>0:
				time.sleep(1)
				counter=counter+1
			if counter==0:
				self.offline_message=f'File {file_name} NOT found'
				print(f'\t [CRASH!] {self.offline_message}')
				return 1
			rsync_command = f"rsync -avz -e ssh {file_name} {user}@{host}:{folder}"
			subprocess.run(rsync_command, shell=True)
			print(f"\t [ОК!] The file {file_name} was sent to the server")
			# удаление файла из текущей папки
			os.remove(file_name)
			if not os.path.exists(file_name):
				print(f"\t [ОК!] The file {file_name} deleted from work folder")
			else:
				self.offline_message=f'File {file_name} NOT deleted'
				print("[CRASH!] {self.offline_message}")
				return 1
		return 0
		
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
	
	def _delta_timer(self, _delta_time):
		'''
		Резрешать периодически чтение вектора данных с устройства
		'''
		event_start_experiment.wait()
		while event_start_experiment.is_set():
			event_up_vector.set()
			time.sleep(_delta_time)
		return 0
		
	def down_options_data(self):
		'''
		Передать на установку (в modbus holding регистры) параметры эксперимента
		'''
		# Проверка режима управления экспериментальным оборудованием (local/remote)
		is_local_mode=1
		service_options=self.experiment_manifest['service_options']
		options_values=service_options['values']
		is_local_mode=options_values['is_local_mode']
		is_local_mode_name=is_local_mode['mb_reg_name']
		is_local_mode_address=is_local_mode['mb_reg_address']
		# TO DO : считать значение регистра и сравнить его с нулем
		
		parameter_category=['time_options','initial_state', 'model_parameters']
		# Формирование значений параметров эксперимента для битовых modbus регистров
		bit_reg_values={} # словарь значений регистров {"номер регистра":"значение",...}
		bit_reg_mask={} # маска битовых регистров
		for name in parameter_category:
			category=self.options_data[name]
			values=category['values']
			for key, value in values.items():
				if value['mb_reg_type']=='bit':	
					reg_address=str(value['mb_reg_address'])
					str_value=value['ws_value']
					if value['mb_dictionary']!=None:
						num_value=value['mb_dictionary'][str_value]
					else:
						num_value=int(str_value)
					
					num_value=int(num_value)<<int(value['mb_decimals'])
					mask=1<<int(value['mb_decimals'])
					if reg_address in bit_reg_values:
						bit_reg_values[reg_address] |= num_value
						bit_reg_mask[reg_address] |= mask
					else:
						bit_reg_values[reg_address]=num_value
						bit_reg_mask[reg_address] = mask
		
		# Запись значений в битовые modbus регистры
		for key, val in bit_reg_values.items():	
			try:
				mask=bit_reg_mask[key]
				old_val=self.dv_connection.read_register(registeraddress=int(key), number_of_decimals=0, functioncode=3)
				new_val=int(((val^old_val)&mask)^old_val) # сохранение других бит регистра и обновление заданных 
				self.dv_connection.write_register(registeraddress=int(key), value=new_val, number_of_decimals=0, functioncode=6)
			except:
				self.offline_message=f'UNABLE to write options data to modbus bit reg{key}={new_val}'
				print(f'\t [CRASH!] {self.offline_message}')
				return 1
						
		# Формирование значений параметров эксперимента для числовых modbus регистров
		reg_values={} # словарь значений регистров {"номер регистра":"значение",...}
		reg_decimals={} # количество знаков после запятой
		for name in parameter_category:
			category=self.options_data[name]
			values=category['values']
			for key, value in values.items():
				if value['mb_reg_type']!='bit':
					reg_address=str(value['mb_reg_address'])
					str_value=value['ws_value']
					if value['mb_dictionary']!=None:
						num_value=value['mb_dictionary'][str_value]
					else:
						num_value=str_value
					reg_values[reg_address]=num_value
					reg_decimals=value['mb_decimals']
		
		# Запись значений в числовые modbus регистры
		for key, val in reg_values.items():	
			try:	
				self.dv_connection.write_register(registeraddress=int(key), value=val, number_of_decimals=0, functioncode=6)
			except:
				self.offline_message=f'UNABLE to write options data to modbus value-register {key}'
				print(f'\t [CRASH!] {self.offline_message}')
				return 1
		
		# Запись в slave признака полученной заявки
		# TO DO
		
		
		print(f'\t [ОК!] Options data down to device')
		return 0
	
	def start_experiment(self):
		'''
		Инициализация запуска эксперимента  
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.status_device}]: ',end=' ')
		print(f'The experiment starting...')
				
		# инициализация видео камеры и запуск процесса записи
		if self._init_videocam()==1:
			return 1
			
		self.thread_read_videocam=threading.Thread(name='thread_read_videocam',\
											  target=self._read_videocam)
		self.thread_read_videocam.daemon = True
		self.thread_read_videocam.start()
								
		# чтение манифеста параметров эксперимента - options_manifest
		options_data=self.options_data['time_options']
		values=options_data['values']
		self.delta_time=values['delta_time']['ws_value']
		
		# настройка длительности эксперимента
		duration_time_str=str(values["duration_time"]["ws_value"])
		duration_type=values["duration_time"]['ws_type']
		if duration_type=='integer':
			self.duration_time=int(duration_time_str)
		elif duration_type=='float':
			self.duration_time=float(duration_time_str)
		
		# Запуск потока установки разрешения чтения вектора данных
		self.thread_delta_timer=threading.Thread(name='thread_delta_timer',\
											  target=self._delta_timer,\
											  args=(self.delta_time,))
		self.thread_delta_timer.daemon = True
		self.thread_delta_timer.start()
		
		# Отправка на сервер времени начала эксперимента 
		try:
			db_cursor=self.db_connection.cursor()
			routin_parameters=[self.device_identifiers['hash_key'], self.fix_claim_id, 'start']
			db_cursor.callproc("push_claim_time",routin_parameters)
			self.db_connection.commit()
			print(f'\t [ОК!] Unix start time push to server')
		except:
			self.offline_message=f'Unix start time NOT push to server'
			print(f'\t [CRASH!] {self.offline_message}')
			return 1
		
		# установка флага начала эксперимента
		event_start_experiment.set()
		
		print(f'\t [OK!] The experiment has start')
		return 0
					
	def finish_experiment(self):
		'''
		Инициализировать окончание эксперимента
		'''
		event_start_experiment.clear()
		self.thread_read_videocam.join()
		self.thread_delta_timer.join()
		
		# Отправка на сервер времени окончания эксперимента 
		try:
			db_cursor=self.db_connection.cursor()
			routin_parameters=[self.device_identifiers['hash_key'], self.fix_claim_id, 'finish']
			db_cursor.callproc("push_claim_time",routin_parameters)
			self.db_connection.commit()
			print(f'\t [ОК!] Unix finish time push to server')
		except:
			self.offline_message=f'Unix finish time NOT push to server'
			print(f'\t [CRASH!] {self.offline_message}')
			return 1
				
		print(f'\t [OK!] The experiment has finished')
		return 0
			
	def get_db_config(self):
		'''
		Получить предыдущий статус контроллера 
		'''
		return self.db_config
	
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
		Получить словарь возможных статусов 
		'''
		return self.status_dictionary
		
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
			print(f'\t [CRASH!] File {_file_name} has NOT been read')
			sys.exit()
	
	def _write_yaml_file(self, _file_name, _data):
		'''
		Записать данные файл в формате .yaml
		'''
		try:
			with open(_file_name, 'w') as file:
				yaml.safe_dump(_data,file, sort_keys=False, allow_unicode=True)
				print(f'\t [ОК!] File {_file_name} has been written')
		except:
			print(f'\t [CRASH!] File {_file_name} has NOT been written')
				
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
			routin_parameters.append(1) # обновление поля date_update (0 -нет, 1 - да)
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
		try:
			db_cursor=self.db_connection.cursor()
			db_cursor.callproc("push_reserve_claims",[hash_key, max_reserved_claims])
			self.db_connection.commit()
		except:
			print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
			f'[waiting connection]...',end='\n')
			return 0
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

	def _read_videocam(self):
		'''
		Реализует фоновую запись видео 
		'''
		event_start_experiment.wait()
		# главный цикл записи видео
		while(event_start_experiment.is_set()):
			ret, frame = self.videocam.read()
			if ret:
				color_yellow = (0,255,255)
				text="Claim id - " + self.fix_claim_id
				cv2.putText(frame, text, (10,20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_yellow, 2)
				self.videocam_out.write(frame)
				
			else:
				self.offline_message=f'Can`t receive video frame'
				print("\t [CRASH!] {self.offline_message}")
				_videocam.release()
				return 1
		# закрытие видеофайла и блокировка камеры
		self.videocam.release()
		self.videocam_out.release()
		return 0	

	
	
	
	
	
										
	def set_keyboard_value(self,_value):
		'''
		Задать принудительно значение набранное на клавиатуре
		'''
		try:
			self.keyboard_value=_value
			return str(self.keyboard_value)
		except:
			print(f'\t [CRASH!] Error in metod set_keyboard_value()')
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
			print(f'\t [CRASH!] {message}')
			self.status_device=self.push_status_device('offline', message)
			print(f'\t Stop controller')
			sys.exit() 
		else:
			print('\t','[OK!] Connected to device by modbus')
	
	def _init_videocam(self):
		'''
		Инициализировать захват видео камеры
		'''
		# параметры временного видео файла
		video_options=self.results_manifest['video_options']
		values=video_options['values']
		extension=values['extension']
		temp_videofile_name=extension['temp_name']
		videofile_extension=extension['value']
		
		# параметры видео камеры 
		codec=values['codec']
		videofile_codec=codec['value']
		fps=values['fps']
		videocam_fps=fps['value']
		size=values['size']
		videocam_size=size['value']
		
		self.videocam = cv2.VideoCapture(1)
		#Error if capture failed
		if not self.videocam.isOpened():
			self.offline_message=f'Can`t capture the videocam'
			print(f'\t [CRASH!] {self.offline_message}')
			return 1
		videocodec=cv2.VideoWriter_fourcc(*videofile_codec)
		temp_videofile_name=temp_videofile_name + '.' + videofile_extension
		self.videocam_out=cv2.VideoWriter(temp_videofile_name, videocodec, videocam_fps, videocam_size)
		print(f'\t [OK!] Video camera captured')
		return 0
		
		
	def _get_args_dataset(self, mb_reg_name='input'):
		'''
		Сформировать словарь аргументов для modbus команды  считывания вектора выходных данных
		из input регистров файла results_manifest
		Возвращает словарь аргументов для modbus команды считывания группы регистров
		'''
		args_dataset_command={}
		# формирование параметров выходных данных - result_manifest.yaml
		dataset_options=self.results_manifest['dataset_options']
		values=dataset_options['values']
		
		# формировние словаря диапазона адресов input регистров 
		# формируется только один диапазон не битовых регистров для считывания
		min_max_registers={'min':65535,'max':0}
		for k, v in values.items():
			if v['mb_reg_type']!='bit' and v['mb_reg_name']==mb_reg_name:
				if v['mb_reg_address']<min_max_registers['min']:
					min_max_registers['min']=v['mb_reg_address']
				if v['mb_reg_address']>min_max_registers['max']:
					min_max_registers['max']=v['mb_reg_address']
		print(f'\t [OK!] Created a list of MIN/MAX modbus address registers: {min_max_registers}')
		#!!! нужно предусмотреть проверку правильности инеми регистров
		
		# формирование словаря аргументов modbus функции для группового считывания выходных регистров данных
		function_code = 4 if mb_reg_name=='input' else (3 if mb_reg_name=='holding' else -1)
		address=min_max_registers['min']
		number=min_max_registers['max']-min_max_registers['min']+1
		mb_args_dataset={'function_code': function_code, 'register_address': address, 'number_of_registers': number}
		print(f'\t [OK!] Created a list of argumentes:\n'
		      f'\t       {mb_args_dataset}')
		return mb_args_dataset
		
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
	
	def up_dataset(self):
		'''
		Считать с объекта весь набор данных эксперимента
		'''	
					
		# формирование выходного вектора
		t=0
		while t<self.duration_time:
			event_up_vector.wait()
			event_up_vector.clear()
			time_start=dt.datetime.now().timestamp()
			try:
				dataset_vector=self.dv_connection.read_registers(registeraddress=self.mb_args_dataset['register_address'],\
																number_of_registers=self.mb_args_dataset['number_of_registers'],\
																functioncode=self.mb_args_dataset['function_code'])	
				time_reading=dt.datetime.now().timestamp()-time_start
				self.dataset.append([time_start, time_reading]+ dataset_vector)
				
				t=t+self.delta_time
			except:
				self.offline_message='Dataset vector NOT read by modbus'
				print(f'\t [CRASH!] {self.offline_message}')
				return 1
		print(f'\t [OK] Data set received from device')
		return 0
	
	def up_dataset_vector(self):
		'''
		Считать с объекта вектор выходных параметров
		'''	
		# формирование аргументов modbus функции чтения input регистров
		self.mb_args_dataset=self._get_args_dataset(mb_reg_name='input')
		address=self.mb_args_dataset['register_address']
		number=self.mb_args_dataset['number_of_registers']
		code=self.mb_args_dataset['function_code']
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
			print(f'\t [CRASH!] {message}')
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
			print(f'\t [CRASH!] {message}')
			self.status_device=self.push_status_device('offline', message)
			print(f'\t Stop controller')
			sys.exit()      
		return dataset_vector
	
	def up_initional_flag(self):
		'''
		Контролировать поднятие флага инициализации установки 
		'''
		initional_flag=0
		# получение информации о максимальном времени ожидания инициализации
		service_options=self.experiment_manifest['service_options']
		options_values=service_options['values']
		max_initional=options_values['max_initional_time']
		max_initional_time=max_initional['value']
		
		# формирование аргументов modbus функции чтения input регистров
		initional_flag=options_values['initional_flag']
		initional_flag_taget=initional_flag['mb_value']
		initional_flag_name=initional_flag['mb_reg_name']
		initional_flag_address=initional_flag['mb_reg_address']
		decimals = 0
		if initional_flag_name=='holding':
			function_code = 3
		elif initional_flag_name=='input':
			function_code = 4
		else:
			self.offline_message=f'Incorrect filling of the service_options category in the experiment_manifest.yaml file'
			print(f'\t [CRASH!] {self.offline_message}')
			return 1
		# задание счетчика
		time_start=dt.datetime.now().timestamp()
		counter=max_initional_time
		# ожидание инициализации
		initional_flag_value=None
		while counter>=0 and initional_flag_value!=initional_flag_taget and self.status_device!='offline':
			print(f'\t Waiting for initional state device ... {counter} sec.  \r',end='')
			try:
				initional_flag_value=self.dv_connection.read_register(registeraddress=initional_flag_address,\
															number_of_decimals=decimals,\
															functioncode=function_code)
			except:
				print(f'\n\t [FAULT!] Connection problem with device                        ')
			counter=int(max_initional_time-(dt.datetime.now().timestamp()-time_start))
		print(f'\n')
		
		if initional_flag_value==initional_flag_taget:
			message=f'Initional state done for {max_initional_time-counter} sec.'
			print(f'\t [OK!] {message}')
			return 0
		elif counter==-1:	
			self.offline_message=f'Initional state wait time out of range'
			print(f'\t [CRASH!] {self.offline_message}')
			return 1
		else:
			return 1
			
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

