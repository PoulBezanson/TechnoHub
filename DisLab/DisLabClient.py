import os.path
import cv2
import numpy
import sys
import time
import datetime
import socket


def video_writer(name, timer):
    #capturing the camera
    vc = cv2.VideoCapture(0)
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
#Port and socket
    host = serverip
    port = 5000
#Creating socket, binding with port
    clientsocket = socket.socket()
    print(f"Connecting with : {host} : {port}")
    clientsocket.connect((host, port))
    print("Connection established...")
    flag = True
    while flag:
        print("Ready to receive time and index")
        data = clientsocket.recv(1024).decode()
        #TEMPR! Data procceding block
        data = data.split("_")
        print(f"Index is {data[0]} with time of {data[1]} seconds, recording the video...")
        #Start writing the video with set up lenth
        fln = video_writer(data[0], float(data[1]))
        # Sending NAME back to server
        print(f"Sending back filename : {os.path.basename(fln)}")
        clientsocket.send(os.path.basename(fln).encode())
        clientsocket.send(str(os.path.getsize(fln)).encode())
        #Sebding video to the server
        print("Sending video to server...")
        with open(fln, "rb") as bfile:
            while True:
                bytes_read = bfile.read(BUFFER)
                if not bytes_read:
                     bfile.close()
                     print("File send: success!")
                     break
                else:
                    clientsocket.sendall(bytes_read)



with open("clientconfig.conf", "r") as f:
    lines = f.readlines()
    ipaddress = lines[0]
    ipaddress = ipaddress.replace("\r", "")
    ipaddress = ipaddress.replace("\n", "")


disLabClient(ipaddress)
