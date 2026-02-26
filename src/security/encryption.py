from cryptography.fernet import Fernet
import os

class ArgosShield:
    def __init__(self):
        self.key_path = "config/master.key"
        if not os.path.exists(self.key_path):
            os.makedirs("config", exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(Fernet.generate_key())
        with open(self.key_path, "rb") as f:
            self.cipher = Fernet(f.read())

    def encrypt(self, data: str):
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, data: str):
        return self.cipher.decrypt(data.encode()).decode()
