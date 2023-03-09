import os.path
import cv2 #https://opencv.org/
import numpy
import sys
import time
import datetime
import socket


def video_writer(name, timer):
    #capturing the camera 
    vc = cv2.VideoCapture("/dev/video1")
    #Error if capture failed
    if not vc.isOpened():
        print("Can`t capture the webcam")
        sys.exit()
    #Setting width and hight of  the frame
    frame_width = int(vc.get(3))
    frame_height = int(vc.get(4))
    #Forming new file name
    fname = name + "_" + str(datetime.date.today())+str(datetime.datetime.now()).replace(":", "-")+".avi"
    vname = "VIDEO/" + fname
    #Setting parameters, codec and framerate
    out = cv2.VideoWriter(vname, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), 20, (frame_width, frame_height))
    start_time = time.time()
    #Starting the recording rimer
    while time.time()-start_time <= timer:
        ret, frame = vc.read()
        if ret:
            out.write(frame)
        else:
            print("Can`t receive frame")
            break
    #Closing file and camera lock
    vc.release()
    out.release()
    return vname



def disLabClient(serverip):
    BUFFER = 4096
#Указываем порт и сокет сервера
    host = socket.gethostname() #Временно локальный сервер
    port = 5000
#Создаем объект сокета и передаём ему сокет и порт
    clientsocket = socket.socket()
    print(f"Connecting with : {host} : {port}")
    clientsocket.connect((host, port))
    print("Connection established...")
    flag = True
    while flag:
        data = clientsocket.recv(1024).decode()
        #Здесь будет блок обработки данных с сервера, предположительно ИД и время
        data = data.split("_")
        #Пишем видео заданного времени
        fln = video_writer(data[0], float(data[1]))
        #Отправляем имя на сервер
        clientsocket.send(os.path.basename(fln).encode())
        #Отправка файла на сервер
        print("Video has been recorded, sending to server...")
        fsize = os.path.getsize(fln)
        with open(fln, "rb") as bfile:
            while True:
                bytes_read = bfile.read(BUFFER)
                if not bytes_read:
                     bfile.close()
                     break
                clientsocket.sendall(bytes_read)
        print("File send: success!")

with open("clientconfig.conf", "r") as f:
    lines = f.readlines()
    ipaddress = lines[0]
disLabClient(ipaddress)
