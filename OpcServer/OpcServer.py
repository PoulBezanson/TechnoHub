#!/home/orangepi/.virtualenvs/envOpcServer/bin/ python3
# -*- coding: utf-8 -*-
#
#  File name: OpcServer.py
#  Virtual Environment: envOpcServer
#  Author: Poul Bezanson

import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html

instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)

#instrument.serial.port                     # this is the serial port name
instrument.serial.baudrate = 9600          # Baud
instrument.serial.bytesize = 8
#instrument.serial.parity   = serial.PARITY_NONE
instrument.serial.stopbits = 1
instrument.serial.timeout  = 0.05          # seconds
#instrument.address                         # this is the slave address number
instrument.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
instrument.clear_buffers_before_each_transaction = True

## Read temperature (PV = ProcessValue) ##

CO2_value=instrument.read_register(0, 0, 4)  # Registernumber, number of decimals
TVOC_value=instrument.read_register(1, 2, 4)
PM1_0_value=instrument.read_register(2, 0, 4)
PM2_5_value=instrument.read_register(3, 0, 4)
PM10_value=instrument.read_register(4, 0, 4)
Temperature_value=instrument.read_register(5, 1, 4)
Humidity_value=instrument.read_register(6, 1, 4)

print('CO2 value = ', CO2_value)
print('TVOC value = ', TVOC_value)
print('PM1.0 value = ', PM1_0_value)
print('PM2.5 value = ', PM2_5_value)
print('PM10 value = ', PM10_value)
print('Temperature value = ', Temperature_value)
print('Humidity value = ', Humidity_value)

