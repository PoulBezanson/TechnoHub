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

import time
#export PYTHONPATH=/home/orangepi/projects/TechnoHub/OpcServer/modules/
import d1_QualityMonitor_class as dv

		
if __name__=="__main__":
	device_1=dv.Device()
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
	
