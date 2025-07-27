from cryptography.fernet import Fernet
from typing import Optional
from .config import settings

class EncryptionManager:
    def __init__(self):
        self.cipher = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize the Fernet cipher with the encryption key"""
        try:
            if settings.ENCRYPTION_KEY:
                self.cipher = Fernet(settings.ENCRYPTION_KEY.encode())
                print("✅ Encryption manager initialized successfully")
            else:
                print("❌ ENCRYPTION_KEY not found in environment variables")
        except Exception as e:
            print(f"❌ Error initializing encryption: {e}")
            self.cipher = None
    
    def encrypt_api_key(self, api_key: str) -> Optional[str]:
        """Encrypt Binance API key"""
        try:
            if not self.cipher:
                return None
            
            encrypted_key = self.cipher.encrypt(api_key.encode())
            return encrypted_key.decode()
            
        except Exception as e:
            print(f"❌ Error encrypting API key: {e}")
            return None
    
    def decrypt_api_key(self, encrypted_key: str) -> Optional[str]:
        """Decrypt Binance API key"""
        try:
            if not self.cipher:
                return None
            
            decrypted_key = self.cipher.decrypt(encrypted_key.encode())
            return decrypted_key.decode()
            
        except Exception as e:
            print(f"❌ Error decrypting API key: {e}")
            return None
    
    def encrypt_api_secret(self, api_secret: str) -> Optional[str]:
        """Encrypt Binance API secret"""
        try:
            if not self.cipher:
                return None
            
            encrypted_secret = self.cipher.encrypt(api_secret.encode())
            return encrypted_secret.decode()
            
        except Exception as e:
            print(f"❌ Error encrypting API secret: {e}")
            return None
    
    def decrypt_api_secret(self, encrypted_secret: str) -> Optional[str]:
        """Decrypt Binance API secret"""
        try:
            if not self.cipher:
                return None
            
            decrypted_secret = self.cipher.decrypt(encrypted_secret.encode())
            return decrypted_secret.decode()
            
        except Exception as e:
            print(f"❌ Error decrypting API secret: {e}")
            return None
    
    def is_ready(self) -> bool:
        """Check if encryption manager is ready to use"""
        return self.cipher is not None

# Global instance
encryption_manager = EncryptionManager()