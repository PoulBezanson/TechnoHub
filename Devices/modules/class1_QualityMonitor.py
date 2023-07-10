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

import time
import datetime as dt
from datetime import datetime
import threading 
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
	def __init__(self):
		'''
		Конструктор
		'''
		self.config_file='./config/1_QualityMonitor.yaml' # файл сетевой конфигурации
		self.device_identifiers=None	# идентификаторы экспериментальной установки
		self.db_connection=None			# коннектор базы данных
		self.db_config=None				# параметры входа в базу данных
		self.status_device='None'    		# текущий статус установки
		self.previus_status_device=None 	# предыдущий статус канала
		self.option_manifest=None    	# структура json со спецификациями эксперимента
		self.state_connection=None   	# структура состояния соединения
		
		
		self.init_controller()
		
	
	def init_controller(self):
		'''
		Инициализировать контроллер эксперимента
		'''
		print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{self.init_controller.__name__}]:')
		# чтение конфигурационного файла .yaml и идентификация установки
		
		with open(self.config_file, 'r') as file:
			config=yaml.safe_load(file)
			print('\t','[ОК!] Configuration file read')
		self.device_identifiers=config['device_identifiers']
				
		# соединение с базой данных сервера
		self.db_config=config['db_config']
		self.db_connection=mysql.connector.connect(
				host=self.db_config["host"],
				user=self.db_config["user"],
				password=self.db_config["password"],
				database=self.db_config["database"])
		if self.db_connection.is_connected():
			print('\t','[OK!] Connected to database')
				
		# запрос последнего статуса (режима) установки из базы данных
		db_cursor=self.db_connection.cursor()
		db_cursor.callproc("pull_status_device",[self.device_identifiers['hash_key']])
		_selection = []	
		for s in db_cursor.stored_results():
			_selection.append(s.fetchall())
		self.previus_status_device=_selection[0][0]
		print(f'\t [ОК!] Last status: {self.previus_status_device[0]}.'
		               f' Тime: {datetime.utcfromtimestamp(int(self.previus_status_device[2])).strftime("%Y-%m-%d %H:%M")}.' 
		               f' Reason: {self.previus_status_device[1]}')
		db_cursor.close()
		
		
		return 0
	
	
	def pull_status_device(self):
		'''
		Запросить из базы данных статус установки 
		'''
		
		# 'TO DO'
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::pull_status_device] ', \
		                                 'Inicialization comlite')
		return status_device
	
	def push_status_device(self):
		'''
		Записать в базу данных статус установки
		'''
		# 'TO DO'
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::push_status_device] ', \
		                                 'Inicialization comlite')
		return 0
	
	def get_status_device(self):
		'''
		Получить текущий статус 
		'''
		return self.status_device
	
	def set_status_device(self,_new_status):
		'''
		Установить новый текущий статус 
		'''
		self.status_device=_new_status
						                                 	
	def push_options_manifest(self):
		'''
		Обновить данные в таблице "experiments" относящиеся к спецификации эксперимента.
		'''
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::push_options_manifest] ', \
		                                 'Inicialization comlite')
		return 0
		
	def delete_claimes(self):
		'''
		Удалить все свободные заявки
		'''
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::delete_claimes] ', \
		                                 'Inicialization comlite')
		return 0
	
	def stop_controller(self):
		'''
		Удалить все свободные заявки
		'''
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::stop_controller] ', \
		                                 'Inicialization comlite')
		return 0
	
	def test_connection(self):
		'''
		Удалить все свободные заявки
		'''
		print(dt.datetime.now().strftime("%Y-%m-%d %H:%M"), \
		                                 '[Device::test_connection] ', \
		                                 'Inicialization comlite')
		return 0
	
	
