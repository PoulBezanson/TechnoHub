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

import sys
sys.path.insert(0, "/home/orangepi/projects/TechnoHub/Devices/modules/")
import datetime as dt
import time
import threading 
import class1_QualityMonitor as dv

if __name__=="__main__":
	'''
	1 этап - организация режима
	'''
	# инициализация контроллера
	device=dv.Device()
	
	# тестировочный блок
	#print('Запуск теста')
	#device.test()
		
	# запуск сканера клавиатуры и ожидание обновления статуса
	scan_keyboard_tread = threading.Thread(target=dv.scan_keyboard, args=(device,))
	scan_keyboard_tread.daemon = True
	scan_keyboard_tread.start()
	while device.get_keyboard_value()=='None':
		pass
	# выбор действия при различных статусах
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[Обновление манифестов]:\n'
			  f'\t [OK!] Waiting for decision...')
	previus_status_id=device.get_previus_status()[3]
	keyboard_status_id=device.get_status_id(device.get_keyboard_value())
		# обновление манифестов при смене статуса "modification" на "online" или "offline" 
	if previus_status_id==3 and (keyboard_status_id==1 or keyboard_status_id==2):
		device.push_all_manifests();
	else:
		print(f'\t [OK!] Manifest file update is not required')
		# удаление заявок при смене статуса на "disposal"
	if keyboard_status_id==4:
		device.push_delete_claims()
		
	
	# обновление в базе данных подтвержденного статуса
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[Обновление в базе данных подтвержденного статуса]:\n'
			  f'\t [OK!] Waiting for push new status...')
	device.push_status_device('Status was confirmed at initialization',device.get_keyboard_value())
	device.set_status_device(device.pull_status_device())
	
	if device.get_status_device()[3] == 2 or device.get_status_device()[3] == 4:
		del device
		print(f'\t [OK!] Stop controller')
		sys.exit()
	print(f'\t [OK!] Stop controller')
	# проверка связи с экспериментальной установкой
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[Установление связи с экспериментальной установкой]:')
	device.set_modbus_connection()
	device.up_dataset_vector()
		
	'''
	2 этап - реализация режима
	'''
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{device.get_keyboard_value()}]:')
	# вход в главный цикл
	while device.get_status_id(device.get_keyboard_value()) == 1 or \
				device.get_status_id(device.get_keyboard_value()) ==  3:
		device.push_reserve_claims()
		
		while device.push_fix_claim()!=0:
			
			# обработка заявки
			device.pull_options_data()
			time.sleep(5)
			
			# обработка режима
			if device.get_status_id(device.get_keyboard_value())==2:
				device.push_unreserve_claims()
				break
			if device.get_status_id(device.get_keyboard_value())==4:
				device.push_delete_claims()
				break
			continue
		
		
		time.sleep(1)
		continue
	device.push_status_device('The status was set in the main loop',device.get_keyboard_value())
	device.set_status_device(device.pull_status_device())	
	print(f'\t [OK!] Stop controller')
	
	
