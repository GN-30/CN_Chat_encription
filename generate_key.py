from cryptography.fernet import Fernet

# Generate a new key
key = Fernet.generate_key()

# Print the key to use in server and client
print("Your encryption key is:")
print(key)

# Optional: Save the key to a file
with open("secret.key", "wb") as key_file:
    key_file.write(key)
    print("Key saved to secret.key")
