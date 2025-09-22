import socket
import threading
from cryptography.fernet import Fernet

# Generate or load key
with open("secret.key", "rb") as key_file:
    key = key_file.read()

cipher = Fernet(key)

# Server setup
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('127.0.0.1', 5555))  # localhost and port
server.listen()
print("Server listening on port 5555...")

clients = []
usernames = []

# Broadcast messages to all clients
def broadcast(message):
    for client in clients:
        client.send(message)

def handle_client(client):
    while True:
        try:
            encrypted_message = client.recv(1024)
            decrypted_message = cipher.decrypt(encrypted_message)
            print(decrypted_message.decode('utf-8'))
            broadcast(encrypted_message)  # send encrypted
        except:
            index = clients.index(client)
            clients.remove(client)
            client.close()
            username = usernames[index]
            broadcast(cipher.encrypt(f"{username} left the chat.".encode()))
            usernames.remove(username)
            break

def receive():
    while True:
        client, address = server.accept()
        print(f"Connected with {str(address)}")

        client.send(cipher.encrypt("USERNAME".encode()))
        username = cipher.decrypt(client.recv(1024)).decode('utf-8')
        usernames.append(username)
        clients.append(client)

        print(f"Username is {username}")
        broadcast(cipher.encrypt(f"{username} joined the chat!".encode()))
        client.send(cipher.encrypt("Connected to server!".encode()))

        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()

print("Server is running...")
receive()
