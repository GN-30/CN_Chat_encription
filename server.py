import socket
import threading
import json
from cryptography.fernet import Fernet
import struct

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
    header = struct.pack('!I', len(message_bytes))
    client_socket.sendall(header + message_bytes)

def create_message(msg_type, content, sender=None, recipient=None):
    message = {'type': msg_type, 'content': content}
    if sender:
        message['sender'] = sender
    if recipient:
        message['recipient'] = recipient
    json_message = json.dumps(message)
    return cipher.encrypt(json_message.encode('utf-8'))

def broadcast_to_all(message_bytes):
    for client in clients:
        send_framed_message(client, message_bytes)

def broadcast_user_list():
    user_list_message = create_message('user_list', usernames)
    broadcast_to_all(user_list_message)

def handle_client(client):
    while True:
        try:
            header = client.recv(4)
            if not header:
                break
            msg_len = struct.unpack('!I', header)[0]
            encrypted_message = client.recv(msg_len)
            
            decrypted_json = cipher.decrypt(encrypted_message).decode('utf-8')
            data = json.loads(decrypted_json)

            if data['type'] == 'whisper':
                recipient_username = data.get('recipient')
                sender_username = data.get('sender')
                
                # Check if the recipient exists
                if recipient_username in usernames:
                    whisper_content = create_message('whisper', data['content'], sender=sender_username, recipient=recipient_username)
                    
                    recipient_index = usernames.index(recipient_username)
                    recipient_socket = clients[recipient_index]
                    send_framed_message(recipient_socket, whisper_content)
                    
                    # Also send back to the sender for their chat history
                    if sender_username in usernames:
                        sender_index = usernames.index(sender_username)
                        sender_socket = clients[sender_index]
                        send_framed_message(sender_socket, whisper_content)
                else:
                    # If recipient doesn't exist, send an error message back to the sender
                    error_msg = create_message('notification', f"User '{recipient_username}' not found.")
                    send_framed_message(client, error_msg)

            elif data['type'] == 'message':
                # This is a public message, broadcast to others
                for c in clients:
                    if c != client:
                        send_framed_message(c, encrypted_message)
        except:
            break
    
    # --- Cleanup when client disconnects ---
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
        try:
            client.send(cipher.encrypt("USERNAME".encode()))
            username = cipher.decrypt(client.recv(1024)).decode('utf-8')
            
            usernames.append(username)
            clients.append(client)
            
            join_message = create_message('notification', f"{username} joined the chat!")
            broadcast_to_all(join_message)
            
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