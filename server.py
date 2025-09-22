# server.py (FINAL VERSION with Message Framing)

import socket
import threading
import json
from cryptography.fernet import Fernet
import struct # For packing integers into bytes

with open("secret.key", "rb") as key_file:
    key = key_file.read()
cipher = Fernet(key)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('127.0.0.1', 5555))
server.listen()
print("Server listening on port 5555...")

clients = []
usernames = []

def send_framed_message(client_socket, message_bytes):
    """Prepares a message with a 4-byte length header and sends it."""
    # Pack the length of the message into a 4-byte integer
    header = struct.pack('!I', len(message_bytes))
    client_socket.sendall(header + message_bytes)

def create_message(msg_type, content, sender=None):
    message = {'type': msg_type, 'content': content}
    if sender:
        message['sender'] = sender
    json_message = json.dumps(message)
    return cipher.encrypt(json_message.encode('utf-8'))

def broadcast_to_all(message_bytes):
    for client in clients:
        send_framed_message(client, message_bytes)

def broadcast_to_others(message_bytes, sender_client):
    for client in clients:
        if client != sender_client:
            send_framed_message(client, message_bytes)

def broadcast_user_list():
    user_list_message = create_message('user_list', usernames)
    broadcast_to_all(user_list_message)

def handle_client(client):
    while True:
        try:
            # The client now handles message framing, server just relays
            header = client.recv(4)
            if not header:
                break
            msg_len = struct.unpack('!I', header)[0]
            encrypted_message = client.recv(msg_len)
            
            # Re-pack and send to others
            full_framed_message = header + encrypted_message
            
            # In a real relay, you might not even decrypt.
            # But here we pass the raw encrypted part to the broadcast function
            # Let's rebuild the framed message for relay
            broadcast_to_others(encrypted_message, sender_client=client)

        except:
            break
    
    # --- Cleanup when loop breaks ---
    if client in clients:
        index = clients.index(client)
        clients.remove(client)
        username = usernames.pop(index)
        print(f"{username} has disconnected.")
        leave_message = create_message('notification', f"{username} left the chat.")
        broadcast_to_all(leave_message)
        broadcast_user_list()
    client.close()

def receive():
    while True:
        client, address = server.accept()
        # Initial handshake is simple string, not framed
        try:
            client.send(cipher.encrypt("USERNAME".encode()))
            username = cipher.decrypt(client.recv(1024)).decode('utf-8')
            
            usernames.append(username)
            clients.append(client)
            
            join_message = create_message('notification', f"{username} joined the chat!")
            broadcast_to_all(join_message)
            
            # Direct messages must also be framed
            connected_msg = create_message('notification', 'Connected to the server!')
            send_framed_message(client, connected_msg)

            broadcast_user_list()

            thread = threading.Thread(target=handle_client, args=(client,))
            thread.start()
        except Exception as e:
            print(f"Failed handshake with {address}: {e}")
            client.close()

print("Server is running...")
receive()