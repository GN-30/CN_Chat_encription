import socket
import threading
from cryptography.fernet import Fernet

# Use the same key as server
# Load key from file
with open("secret.key", "rb") as key_file:
    key = key_file.read()

cipher = Fernet(key)

# Client setup
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 5555))

# Receive messages
def receive():
    while True:
        try:
            message = client.recv(1024)
            decrypted_message = cipher.decrypt(message).decode('utf-8')
            if decrypted_message == "USERNAME":
                client.send(cipher.encrypt(username.encode()))
            else:
                print(decrypted_message)
        except:
            print("An error occurred!")
            client.close()
            break

# Send messages
def write():
    while True:
        message = input('')
        encrypted_message = cipher.encrypt(f"{username}: {message}".encode())
        client.send(encrypted_message)

username = input("Enter your username: ")

# Start threads
receive_thread = threading.Thread(target=receive)
receive_thread.start()

write_thread = threading.Thread(target=write)
write_thread.start()
