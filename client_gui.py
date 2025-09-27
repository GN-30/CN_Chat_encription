import socket
import threading
import customtkinter as ctk
import tkinter
import json
from cryptography.fernet import Fernet
import struct

with open("secret.key", "rb") as key_file:
    key = key_file.read()
cipher = Fernet(key)

class ChatClientGUI(ctk.CTk):
    def __init__(self, username):
        super().__init__()
        
        self.username = username
        self.current_users = []
        
        self.title(f"Secure Chat - Logged in as {username}")
        self.geometry("800x600")
        self.grid_columnconfigure(0, weight=4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ... (Frame and Chat box setup is identical) ...
        self.chat_frame = ctk.CTkFrame(self)
        self.chat_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_box = ctk.CTkTextbox(self.chat_frame, state="disabled", wrap="word")
        self.chat_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.chat_box.tag_config("whisper", foreground="#9370DB")
        self.message_entry = ctk.CTkEntry(self.chat_frame, placeholder_text="Type your message here or use /whisper <user> <message>")
        self.message_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.message_entry.bind("<Return>", self.send_message)

        # --- User List & Settings Frame ---
        self.user_list_frame = ctk.CTkFrame(self, width=200)
        self.user_list_frame.grid(row=0, column=1, rowspan=2, padx=(0, 10), pady=10, sticky="nsew")
        self.user_list_frame.grid_propagate(False)
        self.user_list_label = ctk.CTkLabel(self.user_list_frame, text="Who's Online", font=ctk.CTkFont(weight="bold"))
        self.user_list_label.grid(row=0, column=0, padx=10, pady=10)
        self.appearance_mode_label = ctk.CTkLabel(self.user_list_frame, text="Theme:", anchor="w")
        self.appearance_mode_label.grid(row=99, column=0, padx=10, pady=(10, 0), sticky="s")
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.user_list_frame, values=["Light", "Dark", "System"],
                                                               command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=100, column=0, padx=10, pady=(0,10), sticky="s")
        self.user_list_frame.grid_rowconfigure(98, weight=1)

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
    
    # --- THIS IS THE KEY CHANGE ---
    def update_user_list(self, users):
        self.current_users = users
        for widget in self.user_list_frame.winfo_children():
            if isinstance(widget, ctk.CTkButton):
                widget.destroy()
        
        # Determine all colors based on the current theme
        is_light_mode = ctk.get_appearance_mode().lower() == "light"
        
        # Set colors for the enabled buttons (other users)
        enabled_color = ("#1f1f1f", "#f0f0f0") # (dark_color, light_color)
        
        # Set colors for the disabled button (yourself)
        disabled_color = "gray30" if is_light_mode else "gray75"

        for i, user in enumerate(users):
            is_self = user == self.username
            button_text = f"{user} (You)" if is_self else user

            button = ctk.CTkButton(self.user_list_frame, 
                                   text=button_text,
                                   fg_color="transparent",
                                   anchor="w",
                                   text_color=enabled_color, # Set text color for enabled state
                                   text_color_disabled=disabled_color, # Set text color for disabled state
                                   command=lambda u=user: self.start_whisper(u))
            
            if is_self:
                button.configure(state="disabled")
            else:
                button.bind("<Button-3>", lambda event, u=user: self.show_user_menu(event, u))

            button.grid(row=i + 1, column=0, padx=10, pady=0, sticky="ew")

    # ... (The rest of the file is identical) ...
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

    def receive_messages(self):
        try:
            initial_prompt = self.client_socket.recv(1024)
            if cipher.decrypt(initial_prompt) == b'USERNAME':
                self.client_socket.send(cipher.encrypt(self.username.encode()))
        except Exception as e:
            print(f"Handshake failed: {e}"); self.client_socket.close(); return

        while True:
            try:
                encrypted_message = self.receive_framed_message()
                if encrypted_message is None: break
                message_str = cipher.decrypt(encrypted_message).decode('utf-8')
                data = json.loads(message_str)
                msg_type = data.get('type')
                if msg_type == 'notification':
                    self.after(0, self.add_message_to_box, f"[SYSTEM] {data.get('content')}", "system")
                elif msg_type == 'user_list':
                    self.after(0, self.update_user_list, data.get('content'))
                elif msg_type == 'whisper':
                    sender, content = data.get('sender'), data.get('content')
                    if sender == self.username:
                        formatted_message = f"(Whisper to {data.get('recipient')}): {content}"
                    else:
                        formatted_message = f"(Whisper from {sender}): {content}"
                    self.after(0, self.add_message_to_box, formatted_message, "whisper")
                elif msg_type == 'message':
                    self.after(0, self.add_message_to_box, f"{data.get('sender')}: {data.get('content')}")
            except Exception as e:
                print(f"An error occurred: {e}")
                self.after(0, self.add_message_to_box, "[SYSTEM] Connection lost.", "system")
                self.client_socket.close()
                break

    def send_framed_message(self, message_bytes):
        header = struct.pack('!I', len(message_bytes)); self.client_socket.sendall(header + message_bytes)

    def send_message(self, event=None):
        message_text = self.message_entry.get()
        if not message_text: return
        if message_text.startswith('/whisper '):
            parts = message_text.split(' ', 2)
            if len(parts) < 3:
                self.add_message_to_box("[SYSTEM] Incorrect format. Use /whisper <username> <message>", "system")
                return
            recipient, content = parts[1], parts[2]
            message_data = {'type': 'whisper', 'sender': self.username, 'recipient': recipient, 'content': content}
            self.message_entry.delete(0, "end")
        else:
            self.add_message_to_box(f"You: {message_text}", "own_message")
            self.message_entry.delete(0, "end")
            message_data = {'type': 'message', 'sender': self.username, 'content': message_text}
        json_message = json.dumps(message_data)
        encrypted_message = cipher.encrypt(json_message.encode('utf-8'))
        self.send_framed_message(encrypted_message)

    def on_closing(self):
        self.client_socket.close(); self.destroy()

    def add_message_to_box(self, message, tags=None):
        self.chat_box.configure(state="normal")
        if tags: self.chat_box.insert("end", message + "\n", tags)
        else: self.chat_box.insert("end", message + "\n")
        self.chat_box.configure(state="disabled"); self.chat_box.yview_moveto(1.0)

if __name__ == "__main__":
    username = input("Enter your username: ")
    app = ChatClientGUI(username)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.start()