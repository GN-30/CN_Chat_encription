import socket
import threading
import customtkinter as ctk
import tkinter
import json
from cryptography.fernet import Fernet
import struct
from playsound import playsound
import os
import datetime

class ChatClientGUI(ctk.CTk):
    def __init__(self, username):
        super().__init__()
        
        self.username = username
        self.current_users = []
        self.current_room = "#general" # Default room

        # --- Load Key ---
        with open("secret.key", "rb") as key_file:
            self.key = key_file.read()
        self.cipher = Fernet(self.key)

        self.title(f"Secure Chat - {self.username}")
        self.geometry("1000x600")

        # --- Configure the main grid (3 columns) ---
        self.grid_columnconfigure(0, weight=1, minsize=150)  # Rooms list
        self.grid_columnconfigure(1, weight=5)  # Chat
        self.grid_columnconfigure(2, weight=1, minsize=150)  # Users list
        self.grid_rowconfigure(0, weight=1)

        # --- Rooms Frame (Left) ---
        self.rooms_frame = ctk.CTkFrame(self, width=150)
        self.rooms_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.rooms_label = ctk.CTkLabel(self.rooms_frame, text="Chat Rooms", font=ctk.CTkFont(weight="bold"))
        self.rooms_label.pack(padx=10, pady=10)

        # --- Chat Frame (Center) ---
        self.chat_frame = ctk.CTkFrame(self)
        self.chat_frame.grid(row=0, column=1, padx=0, pady=10, sticky="nsew")
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.chat_box = ctk.CTkTextbox(self.chat_frame, state="disabled", wrap="word")
        self.chat_box.pack(padx=10, pady=10, fill="both", expand=True)
        self.chat_box.tag_config("whisper", foreground="#9370DB")
        
        self.message_entry = ctk.CTkEntry(self.chat_frame, placeholder_text="Type a message or use /join #room")
        self.message_entry.pack(padx=10, pady=(0, 10), fill="x")
        self.message_entry.bind("<Return>", self.send_message)

        # --- User List & Settings Frame (Right) ---
        self.user_list_frame = ctk.CTkFrame(self, width=150)
        self.user_list_frame.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        self.user_list_frame.grid_propagate(False)
        self.user_list_label = ctk.CTkLabel(self.user_list_frame, text="Users in Room", font=ctk.CTkFont(weight="bold"))
        self.user_list_label.pack(padx=10, pady=10)
        
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.user_list_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.pack(padx=10, pady=10, side="bottom")

        # Network setup
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('127.0.0.1', 5555))

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        if new_appearance_mode.lower() == "light":
            self.chat_box.tag_config("system", foreground="gray40")
            self.chat_box.tag_config("own_message", background="#e1e1e1")
        else:
            self.chat_box.tag_config("system", foreground="gray70")
            self.chat_box.tag_config("own_message", background="#2a2d2e")
        self.update_user_list(self.current_users)

    def start(self):
        self.change_appearance_mode_event("Dark")
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()
        self.mainloop()

    def receive_messages(self):
        # Initial handshake
        try:
            initial_prompt = self.cipher.decrypt(self.client_socket.recv(1024))
            if initial_prompt == b'USERNAME':
                self.client_socket.send(self.cipher.encrypt(self.username.encode()))
        except Exception as e:
            print(f"Handshake failed: {e}"); self.client_socket.close(); return

        # Main message loop
        while True:
            try:
                encrypted_message = self.receive_framed_message()
                if not encrypted_message: break
                
                data = json.loads(self.cipher.decrypt(encrypted_message).decode('utf-8'))
                msg_type = data.get('type')

                if msg_type == 'notification':
                    self.after(0, self.add_message_to_box, f"[SYSTEM] {data.get('content')}", "system")
                elif msg_type == 'user_list':
                    self.after(0, self.update_user_list, data.get('content'))
                elif msg_type == 'room_list':
                    self.after(0, self.update_rooms_list, data.get('content'))
                elif msg_type == 'join_success':
                    self.after(0, self.handle_join_success, data.get('content'))
                elif msg_type == 'whisper':
                    sender, content = data.get('sender'), data.get('content')
                    if sender == self.username:
                        formatted_message = f"(Whisper to {data.get('recipient')}): {content}"
                    else:
                        formatted_message = f"(Whisper from {sender}): {content}"
                        self.play_notification_sound()
                    self.after(0, self.add_message_to_box, formatted_message, "whisper")
                elif msg_type == 'message':
                    self.after(0, self.add_message_to_box, f"{data.get('sender')}: {data.get('content')}")
                    self.play_notification_sound()
            except Exception as e:
                print(f"An error occurred: {e}")
                self.after(0, self.add_message_to_box, "[SYSTEM] Connection lost.", "system")
                self.client_socket.close()
                break

    def handle_join_success(self, new_room):
        self.current_room = new_room
        self.title(f"Secure Chat - {self.username} in {self.current_room}")
        self.chat_box.configure(state="normal")
        self.chat_box.delete('1.0', 'end') # Clear chat box on room change
        self.chat_box.configure(state="disabled")
        self.add_message_to_box(f"You have joined {new_room}", "system")

    def update_rooms_list(self, rooms):
        for widget in self.rooms_frame.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                widget.destroy()
        
        is_light_mode = ctk.get_appearance_mode().lower() == "light"
        text_color = "#1f1f1f" if is_light_mode else "#f0f0f0"
        
        for room in rooms:
            button = ctk.CTkButton(self.rooms_frame, text=room, fg_color="transparent",
                                    text_color=text_color, # Apply the fix here
                                    command=lambda r=room: self.join_room_command(r))
            button.pack(padx=10, pady=0, fill="x")
            
    def join_room_command(self, room_name):
        message_data = {'type': 'command', 'content': f"/join {room_name}"}
        self.send_framed_message(json.dumps(message_data))

    def send_message(self, event=None):
        message_text = self.message_entry.get()
        if not message_text: return
        
        message_data = {'type': 'command', 'content': message_text}
        self.send_framed_message(json.dumps(message_data))
        
        if not message_text.startswith('/'):
            self.add_message_to_box(f"You: {message_text}", "own_message")
        
        self.message_entry.delete(0, "end")

    def update_user_list(self, users):
        self.current_users = users
        for widget in self.user_list_frame.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                widget.destroy()
        
        is_light_mode = ctk.get_appearance_mode().lower() == "light"
        enabled_color = "#1f1f1f" if is_light_mode else "#f0f0f0"
        disabled_color = "gray30" if is_light_mode else "gray75"

        for user in users:
            is_self = user == self.username
            button_text = f"{user} (You)" if is_self else user
            button = ctk.CTkButton(self.user_list_frame, text=button_text, fg_color="transparent", anchor="w",
                                   text_color=enabled_color, text_color_disabled=disabled_color,
                                   command=lambda u=user: self.start_whisper(u))
            if is_self:
                button.configure(state="disabled")
            else:
                button.bind("<Button-3>", lambda event, u=user: self.show_user_menu(event, u))
            button.pack(padx=10, pady=0, fill="x")

    def add_message_to_box(self, message, tags=None):
        current_time = datetime.datetime.now().strftime('%H:%M')
        formatted_message = f"[{current_time}] {message}"
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", formatted_message + "\n", tags)
        self.chat_box.configure(state="disabled")
        self.chat_box.yview_moveto(1.0)
    
    def send_framed_message(self, json_string):
        encrypted_message = self.cipher.encrypt(json_string.encode('utf-8'))
        header = struct.pack('!I', len(encrypted_message))
        self.client_socket.sendall(header + encrypted_message)
        
    def play_notification_sound(self):
        try:
            script_dir = os.path.dirname(__file__)
            sound_path = os.path.join(script_dir, 'assets/notification.mp3')
            if os.path.exists(sound_path):
                threading.Thread(target=lambda: playsound(sound_path), daemon=True).start()
            else:
                if not hasattr(self, 'sound_warning_printed'):
                    print("--- Warning: 'notification.mp3' not found. ---")
                    self.sound_warning_printed = True
        except Exception as e:
            print(f"Could not play sound: {e}")

    def show_user_menu(self, event, user):
        if user == self.username: return
        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(label=f"Whisper to {user}", command=lambda: self.start_whisper(user))
        menu.tk_popup(event.x_root, event.y_root)

    def start_whisper(self, user):
        self.message_entry.delete(0, "end"); self.message_entry.insert(0, f"/whisper {user} "); self.message_entry.focus()
    
    def receive_framed_message(self):
        header = self.client_socket.recv(4);
        if not header: return None
        msg_len = struct.unpack('!I', header)[0]
        chunks = []; bytes_recd = 0
        while bytes_recd < msg_len:
            chunk = self.client_socket.recv(min(msg_len - bytes_recd, 2048))
            if not chunk: raise ConnectionError("Socket connection broken")
            chunks.append(chunk); bytes_recd += len(chunk)
        return b''.join(chunks)
        
    def on_closing(self):
        self.client_socket.close(); self.destroy()

if __name__ == "__main__":
    username = input("Enter your username: ")
    app = ChatClientGUI(username)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.start()