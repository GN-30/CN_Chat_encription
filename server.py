import socket
import threading
import json
from cryptography.fernet import Fernet
import struct

class Server:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        
        with open("secret.key", "rb") as key_file:
            self.key = key_file.read()
        self.cipher = Fernet(self.key)

        self.rooms = {"#general": []}
        self.clients = {}
        self.client_to_room = {}

    def send_framed_message(self, client_socket, message_bytes):
        header = struct.pack('!I', len(message_bytes))
        client_socket.sendall(header + message_bytes)

    def create_message(self, msg_type, content, sender=None, recipient=None):
        message = {'type': msg_type, 'content': content}
        if sender: message['sender'] = sender
        if recipient: message['recipient'] = recipient
        json_message = json.dumps(message)
        return self.cipher.encrypt(json_message.encode('utf-8'))

    def broadcast_to_room(self, room_name, message_bytes, exclude_client=None):
        if room_name in self.rooms:
            for client in self.rooms[room_name]:
                if client != exclude_client:
                    self.send_framed_message(client, message_bytes)
    
    def broadcast_user_list(self, room_name):
        if room_name in self.rooms:
            user_list = [self.clients[c] for c in self.rooms[room_name]]
            user_list_msg = self.create_message('user_list', user_list)
            self.broadcast_to_room(room_name, user_list_msg)
            
    def broadcast_room_list(self):
        room_list = list(self.rooms.keys())
        room_list_msg = self.create_message('room_list', room_list)
        for client in self.clients.keys():
            self.send_framed_message(client, room_list_msg)

    def handle_command(self, command_str, client):
        parts = command_str.split(' ', 1)
        action = parts[0].lower()
        sender_username = self.clients.get(client)
        
        if action == "/join":
            if len(parts) > 1 and parts[1].startswith('#'):
                self.join_room(client, parts[1])
            else:
                msg = self.create_message('notification', "Invalid format. Use /join #roomname")
                self.send_framed_message(client, msg)
        
        elif action == "/list":
            room_list = list(self.rooms.keys())
            msg = self.create_message('notification', f"Available rooms: {', '.join(room_list)}")
            self.send_framed_message(client, msg)

        # --- THIS IS THE LOGIC THAT WAS MISSING FROM YOUR FILE ---
        elif action == "/whisper":
            whisper_parts = command_str.split(' ', 2)
            if len(whisper_parts) < 3:
                msg = self.create_message('notification', "Invalid format. Use /whisper <username> <message>")
                self.send_framed_message(client, msg)
                return
            
            recipient_username = whisper_parts[1]
            content = whisper_parts[2]

            if recipient_username in self.clients.values():
                recipient_socket = next((sock for sock, name in self.clients.items() if name == recipient_username), None)
                if recipient_socket:
                    whisper_msg = self.create_message('whisper', content, sender=sender_username, recipient=recipient_username)
                    self.send_framed_message(recipient_socket, whisper_msg)
                    self.send_framed_message(client, whisper_msg) # Send confirmation to sender
            else:
                error_msg = self.create_message('notification', f"User '{recipient_username}' not found.")
                self.send_framed_message(client, error_msg)
        
        else: # Regular message
            current_room = self.client_to_room.get(client)
            if current_room:
                msg_bytes = self.create_message('message', command_str, sender=sender_username)
                self.broadcast_to_room(current_room, msg_bytes, exclude_client=client)

    def join_room(self, client, new_room):
        username = self.clients.get(client)
        old_room = self.client_to_room.get(client)

        if old_room == new_room: return

        if old_room:
            self.rooms[old_room].remove(client)
            leave_msg = self.create_message('notification', f"{username} left the room.")
            self.broadcast_to_room(old_room, leave_msg)
            self.broadcast_user_list(old_room)

        if new_room not in self.rooms:
            self.rooms[new_room] = []
            self.broadcast_room_list()
        
        self.rooms[new_room].append(client)
        self.client_to_room[client] = new_room
        
        join_msg = self.create_message('notification', f"{username} joined {new_room}.")
        self.broadcast_to_room(new_room, join_msg)
        self.broadcast_user_list(new_room)
        
        success_join_msg = self.create_message('join_success', new_room)
        self.send_framed_message(client, success_join_msg)

    def handle_client(self, client):
        try:
            while True:
                header = client.recv(4)
                if not header: break
                msg_len = struct.unpack('!I', header)[0]
                encrypted_message = client.recv(msg_len)
                data = json.loads(self.cipher.decrypt(encrypted_message).decode('utf-8'))
                
                content = data.get('content')
                self.handle_command(content, client)
        finally:
            self.remove_client(client)

    def remove_client(self, client):
        if client in self.clients:
            username = self.clients[client]
            room = self.client_to_room.get(client)
            del self.clients[client]
            if client in self.client_to_room: del self.client_to_room[client]
            
            if room and client in self.rooms.get(room, []):
                self.rooms[room].remove(client)
                leave_msg = self.create_message('notification', f"{username} has disconnected.")
                self.broadcast_to_room(room, leave_msg)
                self.broadcast_user_list(room)
            
            print(f"{username} has disconnected.")
            client.close()

    def start(self):
        print(f"Server listening on {self.host}:{self.port}...")
        self.server_socket.listen()
        while True:
            client, address = self.server_socket.accept()
            try:
                client.send(self.cipher.encrypt("USERNAME".encode()))
                username = self.cipher.decrypt(client.recv(1024)).decode('utf-8')
                self.clients[client] = username
                self.join_room(client, "#general")
                self.broadcast_room_list()
                
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.start()
            except Exception as e:
                print(f"Failed handshake with {address}: {e}"); client.close()

if __name__ == '__main__':
    server = Server()
    server.start()