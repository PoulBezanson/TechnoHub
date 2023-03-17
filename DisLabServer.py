import os.path
import socket
import threading

#Reading configs
with open("serverconfig.conf", "r") as f:
    lines = f.readlines()
    ipaddress = lines[0]
    ipaddress = ipaddress.replace("\r", "")
    ipaddress = ipaddress.replace("\n", "")
#Setting adress and port for a server
host = ipaddress
port = 5000
SADDRESS = (host, port)
eqflag = False
serversocket = socket.socket()
serversocket.bind(SADDRESS)
HEADER = 65
#Clients list
client_list =[]
print("-=DisLab Server Active=-")


def connector():
    serversocket.listen()
    while True:
        eqflag = False
        connect, address = serversocket.accept()
        for i in range(len(client_list)):
            if client_list[i][1] == address:
                eqflag = True
        if eqflag == False:
            client_list.append((connect, address))
        print(f"  \r\n >>New client: {address}")
        print(f"Clients: {threading.active_count() - 2}")


def disLabServer(conn, addr):
    BUFFER = 4096
    # Getting filename from the client
    idname = conn.recv(BUFFER).decode()
    fsize = int(conn.recv(BUFFER).decode())
    print(f"Filename received : {idname} size of {fsize} byte")
    # Getting file from the client
    with open(f"REC/{idname}", "wb") as fl:
        rcv = 0;
        while (rcv<=fsize):
            bytes_read = conn.recv(BUFFER)
            fl.write(bytes_read)
            rcv = rcv + int(BUFFER)
    print(">>File Received successful!")



def DB_IMMITATE():
    conloop = threading.Thread(target=connector)
    conloop.start()
    while True:
        for x in range(len(client_list)):
            print(f"{x} - {client_list[x]}")
        commun = input("Ask the client? Y/N")
        if commun == "Y":
            con_id = input("Choose the client index, starting from 0")
            while True:
                cid = input("Enter your ID : ")
                time = input("Enter video lenth in seconds : ")
                data = str(cid) + "_" + str(time)
                # Sending data to current client
                client_list[int(con_id)][0].send(data.encode())
                # Creating thread for a new file pick up
                thread = threading.Thread(target=disLabServer, args=(client_list[int(con_id)][0], client_list[int(con_id)][1]))
                thread.start()

                end_c = input("Ask client again? Y/N")
                if end_c != "Y":
                    break
        end = input("Proceed? Y/N")
        print("Client list : ")
        if end != "Y":
            break


DB_IMMITATE()