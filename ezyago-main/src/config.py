import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

class Settings:
    # --- Firebase Configuration ---
    FIREBASE_CREDENTIALS_JSON: str = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FIREBASE_DATABASE_URL: str = os.getenv("FIREBASE_DATABASE_URL", "https://aviatoronline-6c2b4-default-rtdb.firebaseio.com")
    
    # --- Encryption ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")  # Master key for API encryption
    
    # --- Admin Configuration ---
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "bilwininc@gmail.com")
    ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBdXzgVB/VGO5i")  # Default: admin123456
    
    @classmethod
    def get_admin_password_hash(cls) -> str:
        """Get admin password hash, create from plain password if needed"""
        # If ADMIN_PASSWORD is set (plain text), hash it
        plain_password = os.getenv("ADMIN_PASSWORD")
        if plain_password:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.hash(plain_password)
        
        # Otherwise use the hash directly
        return cls.ADMIN_PASSWORD_HASH
    
    # --- Payment Configuration ---
    USDT_WALLET_ADDRESS: str = os.getenv("USDT_WALLET_ADDRESS", "TYourUSDTWalletAddressHere")
    
    # --- JWT Configuration ---
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    
    # --- Trading Configuration ---
    LEVERAGE: int = 10
    ORDER_SIZE_USDT: float = 25.0
    TIMEFRAME: str = "15m"
    STOP_LOSS_PERCENT: float = 0.04
    
    # --- Subscription Configuration ---
    TRIAL_DAYS: int = 7
    SUBSCRIPTION_PRICE_USDT: float = 10.0
    SUBSCRIPTION_DAYS: int = 30
    
    # --- Binance Configuration ---
    BINANCE_BASE_URL_LIVE = "https://fapi.binance.com"
    BINANCE_BASE_URL_TEST = "https://testnet.binancefuture.com"
    BINANCE_WS_URL_LIVE = "wss://fstream.binance.com"
    BINANCE_WS_URL_TEST = "wss://stream.binancefuture.com"
    
    # --- Rate Limiting ---
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 1 hour
    
    # --- Security ---
    ALLOWED_HOSTS: list = ["ezyago.com", "www.ezyago.com", "*.onrender.com"] if os.getenv("ENVIRONMENT") == "production" else ["*"]
    
    # --- Environment ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # --- Email Configuration (for future use) ---
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    @property
    def fernet_cipher(self):
        """Returns Fernet cipher for encryption/decryption"""
        if not self.ENCRYPTION_KEY:
            print("⚠️ ENCRYPTION_KEY not set, generating temporary key")
            # Generate a temporary key for development
            temp_key = Fernet.generate_key()
            return Fernet(temp_key)
        
        try:
            # Try to use the provided key
            return Fernet(self.ENCRYPTION_KEY.encode())
        except Exception as e:
            print(f"⚠️ Invalid ENCRYPTION_KEY: {e}")
            # Generate a temporary key as fallback
            temp_key = Fernet.generate_key()
            return Fernet(temp_key)

settings = Settings()