import threading
import sys
import termios
import tty

# Функция, которая будет выполняться в фоновом режиме для опроса клавиатуры
mystat=True
def keyboard_listener():
	global mystat
	# Получаем текущие настройки терминала
	old_settings = termios.tcgetattr(sys.stdin)
	statuses=['online','offline','modifity','disposal']
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
				print(chars+'*')
				for x in statuses:
					print(x)
					if chars[:symbol]==x[:symbol]:
						if symbol<len(x):
							symbol=symbol+1
							update=False
							break
						else:
							if symbol==len(x):
								print(chars,'!!!')
								mystat=False
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

# Основная программа
def main_program():
	print("Основная программа запущена.")

	# Создаем и запускаем поток для опроса клавиатуры
	keyboard_thread = threading.Thread(target=keyboard_listener)
	keyboard_thread.daemon = True
	keyboard_thread.start()

	# Здесь можно добавить вашу основную логику программы

	# Пример: просто ждем, пока не будет нажата клавиша 'q'
	while mystat==True:
		print(1)

if __name__ == "__main__":
	main_program()
