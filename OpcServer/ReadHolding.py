import minimalmodbus #https://minimalmodbus.readthedocs.io/en/master/index.html
import time

def main(args):
	print("Hellow!")
	instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 100)  # port name, slave address (in decimal)
	instrument.serial.baudrate = 9600         # Baud
	instrument.serial.bytesize = 8
	instrument.serial.stopbits = 1
	instrument.serial.timeout  = 0.1          # seconds
	instrument.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
	instrument.clear_buffers_before_each_transaction = True 
	while True:
		instrument.write_register(registeraddress=16, value=0, number_of_decimals=0, functioncode=6)
		instrument.write_register(registeraddress=17, value=2, number_of_decimals=0, functioncode=6)
		LCD=instrument.read_register(registeraddress=16, number_of_decimals=0, functioncode=3) # (Register number, number of decimals, Holding register)
		holding_reg17=instrument.read_register(registeraddress=17, number_of_decimals=0, functioncode=3)
		mute_state=holding_reg17 & 1
		unit_state=(holding_reg17 & 2)>>1
		print(f"Mute - {mute_state}   Unit - {unit_state}")
		time.sleep(1)
	return 0

if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))
