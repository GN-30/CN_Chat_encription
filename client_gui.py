# client_gui.py (FINAL VERSION with Message Framing)

import socket
import threading
import customtkinter as ctk
import json
from cryptography.fernet import Fernet
import struct

with open("secret.key", "rb") as key_file:
    key = key_file.read()
cipher = Fernet(key)

class ChatClientGUI(ctk.CTk):
    def __init__(self, username):
        super().__init__()
        # ... (GUI setup is identical to before, no changes needed here) ...
        self.username = username
        self.title(f"Secure Chat - Logged in as {username}")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.chat_frame = ctk.CTkFrame(self)
        self.chat_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_box = ctk.CTkTextbox(self.chat_frame, state="disabled", wrap="word")
        self.chat_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.message_entry = ctk.CTkEntry(self.chat_frame, placeholder_text="Type your message here...")
        self.message_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.message_entry.bind("<Return>", self.send_message)
        self.user_list_frame = ctk.CTkFrame(self, width=200)
        self.user_list_frame.grid(row=0, column=1, rowspan=2, padx=(0, 10), pady=10, sticky="nsew")
        self.user_list_frame.grid_propagate(False)
        self.user_list_frame.grid_rowconfigure(1, weight=1)
        self.user_list_label = ctk.CTkLabel(self.user_list_frame, text="Who's Online", font=ctk.CTkFont(weight="bold"))
        self.user_list_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('127.0.0.1', 5555))

    def start(self):
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()
        self.mainloop()

    def receive_framed_message(self):
        """Receives a message with a 4-byte length header."""
        header = self.client_socket.recv(4)
        if not header:
            return None
        msg_len = struct.unpack('!I', header)[0]

        # Receive data in a loop until the full message is received
        chunks = []
        bytes_recd = 0
        while bytes_recd < msg_len:
            chunk = self.client_socket.recv(min(msg_len - bytes_recd, 2048))
            if not chunk:
                raise ConnectionError("Socket connection broken")
            chunks.append(chunk)
            bytes_recd += len(chunk)
        return b''.join(chunks)

    def receive_messages(self):
        # Initial handshake is not framed, handle it separately
        try:
            initial_prompt = self.client_socket.recv(1024)
            if cipher.decrypt(initial_prompt) == b'USERNAME':
                self.client_socket.send(cipher.encrypt(self.username.encode()))
        except Exception as e:
            print(f"Handshake failed: {e}")
            self.client_socket.close()
            return

        # All subsequent messages are framed
        while True:
            try:
                encrypted_message = self.receive_framed_message()
                if encrypted_message is None:
                    break
                
                message_str = cipher.decrypt(encrypted_message).decode('utf-8')
                data = json.loads(message_str)
                
                msg_type = data.get('type')
                if msg_type == 'notification':
                    self.after(0, self.add_message_to_box, f"[SYSTEM] {data.get('content')}")
                elif msg_type == 'user_list':
                    self.after(0, self.update_user_list, data.get('content'))
                elif msg_type == 'message':
                    self.after(0, self.add_message_to_box, f"{data.get('sender')}: {data.get('content')}")
            except Exception as e:
                print(f"An error occurred: {e}")
                self.after(0, self.add_message_to_box, "[SYSTEM] Connection lost.")
                self.client_socket.close()
                break

    def send_framed_message(self, message_bytes):
        """Prepares a message with a 4-byte length header and sends it."""
        header = struct.pack('!I', len(message_bytes))
        self.client_socket.sendall(header + message_bytes)

    def send_message(self, event=None):
        message_text = self.message_entry.get()
        if message_text:
            self.add_message_to_box(f"You: {message_text}")
            self.message_entry.delete(0, "end")
            
            message_data = {'type': 'message', 'sender': self.username, 'content': message_text}
            json_message = json.dumps(message_data)
            encrypted_message = cipher.encrypt(json_message.encode('utf-8'))
            self.send_framed_message(encrypted_message)

    def on_closing(self):
        self.client_socket.close()
        self.destroy()

    # ... other functions (update_user_list, add_message_to_box) are the same ...
    def update_user_list(self, users):
        for widget in self.user_list_frame.winfo_children():
            if widget != self.user_list_label:
                widget.destroy()
        for i, user in enumerate(users):
            label = ctk.CTkLabel(self.user_list_frame, text=user, anchor="w")
            label.grid(row=i+1, column=0, padx=10, pady=2, sticky="ew")

    def add_message_to_box(self, message):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", message + "\n")
        self.chat_box.configure(state="disabled")
        self.chat_box.yview_moveto(1.0)

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    username = input("Enter your username: ")
    app = ChatClientGUI(username)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.start()