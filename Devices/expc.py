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
import expc_class as dv

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
	thread_scan_keyboard = threading.Thread(target=dv.scan_keyboard, args=(device, device.get_db_config(),))
	thread_scan_keyboard.daemon = True
	thread_scan_keyboard.start()
		
	# ожидание начальной инициализации статуса
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		  f'[Enter new status...]:')
	if device.pull_status_device()!=0:
		pass
	print(f'\t          ',end='')
	status_dictionary=device.get_status_dictionary()
	for key, value in status_dictionary.items():
		print(f'"{key}" ', end='')
	print('\n')
	while device.get_status_device()==None:
		pass
	
	#device.push_status_device(device.get_status_device(),'Status set by operator')
					
	# обновление манифестов при смене статуса "modification" на "online" или "offline" 
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{device.get_status_device()}]: Manifests update...')
	device.push_all_manifests()
	
	# удаление заявок при смене статуса на "disposal"
	if device.get_status_device()=='disposal':
		device.push_delete_claims()
	
	# проверка условия завершения работы контроллера
	if device.get_status_device()=='offline' or device.get_status_device()=='disposal':
		print(f'\t       Stop controller')
		del device
		sys.exit()
		
	# проверка связи с экспериментальной установкой
	print(f'{dt.datetime.now().strftime("%Y-%m-%d %H:%M")} '
		      f'[{device.get_status_device()}]: Connection with device...')
	device.set_modbus_connection()
	device.up_dataset_vector()
		
	'''
	2 этап - реализация режима
	'''
	
	# вход в главный цикл
	#!!! предусмотреть возможность запрета перехода между режимами 1 и 3 
	
	while device.get_status_device()=='online' or \
				device.get_status_device()=='modification':
		if device.push_reserve_claims()!=0:
			while device.push_fix_claim()!=0:
				# обработка заявки
				if device.pull_options_data()==0: 
					if device.down_options_data()==0:
						if device.up_initional_flag()==0:
							if device.start_experiment()==0:
								if device.up_dataset()==0:
									if device.finish_experiment()==0:
										if device.processing_dataset()==0:
											if device.push_data_files()==0:
												# TO DO
												# обработка введного режима
												if device.get_status_device()=='offline':
													device.push_unreserve_claims()
													break
												continue
				device.push_unfix_claim()
				device.push_unreserve_claims()
				if device.get_status_device()!='offline':
					device.status_device=device.push_status_device('offline', device.offline_message, device.db_config)
				sys.exit()
					
		# выход из главного цикла при modification и disposal
		# проверка изменения статуса на сервером другими контроллерами
		time.sleep(1) # задержка обращения к базе даных
		pull_status=device.pull_status_device(print_message=False)
		if pull_status!=device.get_status_device():
			device.set_status_device(pull_status)
		if device.get_status_device()=='modification' and device.push_reserve_claims()==0:
			break
		if device.get_status_device()=='disposal':
			device.push_delete_claims()
			break
		#continue
	print(f'\n\t         Stop controller')
	
	
