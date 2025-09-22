import socket
import threading
import customtkinter as ctk
from cryptography.fernet import Fernet

# --- Same encryption and key loading as before ---
with open("secret.key", "rb") as key_file:
    key = key_file.read()
cipher = Fernet(key)

# --- GUI Application Class ---
class ChatClientGUI(ctk.CTk):
    def __init__(self, username):
        super().__init__()
        self.username = username
        
        self.title(f"Secure Chat - Logged in as {username}")
        self.geometry("700x500")

        # --- Configure the grid layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Create Widgets ---
        # Chat display box
        self.chat_box = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.chat_box.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Message entry box
        self.message_entry = ctk.CTkEntry(self, placeholder_text="Type your message here...")
        self.message_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        # Bind the Enter key to the send_message function
        self.message_entry.bind("<Return>", self.send_message)

        # Send button (optional, as Enter key works)
        # self.send_button = ctk.CTkButton(self, text="Send", command=self.send_message)
        # self.send_button.grid(row=2, column=0, padx=10, pady=(0,10), sticky="ew")

        # --- Initialize Network Connection ---
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('127.0.0.1', 5555))

    def start(self):
        """Starts the receive thread and the GUI main loop."""
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()
        self.mainloop()

    def receive_messages(self):
        """Handles receiving messages from the server in a loop."""
        while True:
            try:
                encrypted_message = self.client_socket.recv(1024)
                if not encrypted_message:
                    break
                
                decrypted_message = cipher.decrypt(encrypted_message).decode('utf-8')

                if decrypted_message == "USERNAME":
                    # Server is asking for our username
                    self.client_socket.send(cipher.encrypt(self.username.encode()))
                else:
                    # We have a regular message, schedule it to be added to the GUI
                    self.after(0, self.add_message_to_box, decrypted_message)

            except Exception as e:
                print(f"An error occurred in receive_messages: {e}")
                self.after(0, self.add_message_to_box, "[SYSTEM] Connection lost.")
                self.client_socket.close()
                break

    def add_message_to_box(self, message):
        """Safely adds a message to the chat box from the main GUI thread."""
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", message + "\n")
        self.chat_box.configure(state="disabled")
        self.chat_box.yview_moveto(1.0) # Auto-scroll to the bottom

    def send_message(self, event=None):
        """Handles sending a message to the server."""
        message = self.message_entry.get()
        if message:
            # Clear the entry box
            self.message_entry.delete(0, "end")
            
            # Format and encrypt the message
            full_message = f"{self.username}: {message}"
            encrypted_message = cipher.encrypt(full_message.encode('utf-8'))
            
            # Send to the server
            self.client_socket.send(encrypted_message)

    def on_closing(self):
        """Handles the window closing event."""
        self.client_socket.close()
        self.destroy()

# --- Main execution block ---
if __name__ == "__main__":
    # Set the appearance mode
    ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
    ctk.set_default_color_theme("blue")

    # We still need to ask for the username in the console first
    username = input("Enter your username: ")

    app = ChatClientGUI(username)
    app.protocol("WM_DELETE_WINDOW", app.on_closing) # Handle window close
    app.start()