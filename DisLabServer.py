import os.path
import socket
import threading

#Установка адреса и порта для сервера, биндинг
host = socket.gethostbyname(socket.gethostname())  # заменить на Айпи
port = 5000
ADDRESS = (host, port)
serversocket = socket.socket()
serversocket.bind(ADDRESS)
HEADER = 65
#Clients list
client_list =[]
print("-=DisLab Server Active=-")


def connector():
    serversocket.listen()
    while True:
        connect, address = serversocket.accept()
        client_list.append((connect, address))
        print(f"New client: {connect}")
        thread = threading.Thread(target=disLabServer, args=(connect, address))
        thread.start()
        print(f"Clients: {threading.active_count() - 2}")


def disLabServer(conn, addr):
    BUFFER = 4096
    idname = conn.recv(BUFFER).decode()
    # Getting file from the client
    with open(f"REC/{idname}", "wb+") as fl:
        while True:
            bytes_read = conn.recv(BUFFER)
            if not bytes_read:
                fl.close()
                print("File recieved!")
                break
            fl.write(bytes_read)


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
                client_list[int(con_id)][0].send(data.encode()) #текущий клиент
                end_c = input("Ask client again? Y/N")
                if end_c != "Y":
                    break
        end = input("Proceed? Y/N")
        if end != "Y":
            break


DB_IMMITATE()