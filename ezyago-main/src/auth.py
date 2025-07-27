from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import uuid
from .config import settings
from .database import firebase_manager
from .models import UserData, UserRole
import firebase_admin
from firebase_admin import auth as firebase_auth

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

class AuthManager:
    def __init__(self):
        self.pwd_context = pwd_context
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None
    
    def generate_verification_token(self) -> str:
        """Generate a random verification token"""
        return secrets.token_urlsafe(32)
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserData]:
        """Authenticate a user with email and password"""
        try:
            # Special handling for admin user
            if email == settings.ADMIN_EMAIL:
                admin_password_hash = settings.get_admin_password_hash()
                if self.verify_password(password, admin_password_hash):
                    # Create or get admin user
                    admin_user = await firebase_manager.get_user_by_email(email)
                    if not admin_user:
                        # Create admin user if doesn't exist
                        from .models import UserRole, SubscriptionStatus
                        admin_data = UserData(
                            uid="admin-" + str(uuid.uuid4()),
                            email=email,
                            password_hash=admin_password_hash,
                            full_name="Admin User",
                            role=UserRole.ADMIN,
                            subscription_status=SubscriptionStatus.ACTIVE,
                            trial_end_date=datetime.utcnow() + timedelta(days=365),
                            created_at=datetime.utcnow()
                        )
                        await firebase_manager.create_user(admin_data)
                        admin_user = admin_data
                    
                    print(f"✅ Admin authenticated: {email}")
                    return admin_user
                else:
                    print(f"❌ Invalid admin password: {email}")
                    return None
            
            # First check if user exists in Firebase Authentication
            try:
                firebase_user = firebase_auth.get_user_by_email(email)
                print(f"✅ Firebase Auth user found: {email}")
            except firebase_auth.UserNotFoundError:
                print(f"❌ User not found in Firebase Auth: {email}")
                return None
            except Exception as e:
                print(f"❌ Firebase Auth lookup error: {e}")
                return None
            
            # Get user from Realtime Database
            user = await firebase_manager.get_user_by_email(email)
            if not user:
                print(f"❌ User not found in database: {email}")
                return None
            
            # Verify password
            if not self.verify_password(password, user.password_hash):
                print(f"❌ Invalid password for user: {email}")
                return None
            
            # Update last login
            await firebase_manager.update_user(user.uid, {
                'last_login': datetime.utcnow()
            })
            
            print(f"✅ User authenticated successfully: {email}")
            return user
            
        except Exception as e:
            print(f"❌ Authentication error for {email}: {e}")
            return None
    
    async def register_user(self, email: str, password: str, full_name: str, language: str = "tr") -> Optional[UserData]:
        """Register a new user"""
        try:
            print(f"🔄 Starting registration for: {email}")
            
            # Check if user already exists in Realtime Database
            existing_user = await firebase_manager.get_user_by_email(email)
            if existing_user:
                print(f"❌ User already exists in database: {email}")
                return None
            
            # Validate password strength
            if len(password) < 6:
                print(f"❌ Password too weak for {email}")
                raise ValueError("Password must be at least 6 characters long")
            
            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                print(f"❌ Invalid email format: {email}")
                raise ValueError("Invalid email format")
            
            # First, create user in Firebase Authentication
            try:
                print(f"🔄 Creating Firebase Auth user for: {email}")
                firebase_user = firebase_auth.create_user(
                    email=email,
                    password=password,
                    display_name=full_name,
                    email_verified=False
                )
                print(f"✅ Firebase Auth user created: {firebase_user.uid}")
                
            except firebase_auth.EmailAlreadyExistsError:
                print(f"❌ Email already exists in Firebase Auth: {email}")
                return None
            except firebase_auth.WeakPasswordError as e:
                print(f"❌ Weak password error: {e}")
                return None
            except firebase_auth.InvalidEmailError as e:
                print(f"❌ Invalid email error: {e}")
                return None
            except Exception as e:
                print(f"❌ Firebase Auth creation error: {e}")
                return None
            
            # If Firebase Auth creation successful, create user in Realtime Database
            print(f"🔄 Creating user in Realtime Database for: {email}")
            password_hash = self.get_password_hash(password)
            verification_token = self.generate_verification_token()
            
            user_data = UserData(
                uid=firebase_user.uid,  # Use Firebase Auth UID
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                language=language,
                email_verification_token=verification_token,
                created_at=datetime.utcnow(),
                trial_end_date=datetime.utcnow() + timedelta(days=settings.TRIAL_DAYS)
            )
            
            # Create user in Realtime Database
            success = await firebase_manager.create_user(user_data)
            if success:
                print(f"✅ User created successfully in database: {email}")
                return user_data
            else:
                # If database creation fails, delete from Firebase Auth
                try:
                    firebase_auth.delete_user(firebase_user.uid)
                    print(f"🧹 Cleaned up Firebase Auth user after database failure: {email}")
                except Exception as cleanup_error:
                    print(f"❌ Failed to cleanup Firebase Auth user: {cleanup_error}")
                return None
                
        except Exception as e:
            print(f"❌ Registration error for {email}: {e}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            return None
    
    async def verify_email(self, token: str) -> bool:
        """Verify user email with token"""
        try:
            # Find user by verification token
            users_ref = firebase_manager.db_ref.child('users')
            users_data = users_ref.order_by_child('email_verification_token').equal_to(token).get()
            
            if not users_data:
                return False
            
            uid = list(users_data.keys())[0]
            
            # Update user as verified
            await firebase_manager.update_user(uid, {
                'email_verified': True,
                'email_verification_token': None
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error verifying email: {e}")
            return False
    
    async def request_password_reset(self, email: str) -> Optional[str]:
        """Request password reset and return reset token"""
        user = await firebase_manager.get_user_by_email(email)
        if not user:
            return None
        
        reset_token = self.generate_verification_token()
        reset_expires = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        
        await firebase_manager.update_user(user.uid, {
            'password_reset_token': reset_token,
            'password_reset_expires': reset_expires
        })
        
        return reset_token
    
    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password with token"""
        try:
            # Find user by reset token
            users_ref = firebase_manager.db_ref.child('users')
            users_data = users_ref.order_by_child('password_reset_token').equal_to(token).get()
            
            if not users_data:
                return False
            
            uid = list(users_data.keys())[0]
            user_data = users_data[uid]
            
            # Check if token is expired
            if user_data.get('password_reset_expires'):
                expires = datetime.fromisoformat(user_data['password_reset_expires'])
                if expires <= datetime.utcnow():
                    return False
            
            # Update password
            new_password_hash = self.get_password_hash(new_password)
            await firebase_manager.update_user(uid, {
                'password_hash': new_password_hash,
                'password_reset_token': None,
                'password_reset_expires': None
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            return False

# Global instance
auth_manager = AuthManager()

# Dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserData:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = auth_manager.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        uid: str = payload.get("sub")
        if uid is None:
            raise credentials_exception
        
    except JWTError:
        raise credentials_exception
    
    user = await firebase_manager.get_user(uid)
    if user is None:
        raise credentials_exception
    
    # Check if user is blocked
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked"
        )
    
    return user

async def get_current_admin(current_user: UserData = Depends(get_current_user)) -> UserData:
    """Get current authenticated admin user"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def get_active_user(current_user: UserData = Depends(get_current_user)) -> UserData:
    """Get current user with active subscription"""
    from .models import SubscriptionStatus
    
    # Check subscription status
    if current_user.subscription_status == SubscriptionStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription expired. Please renew your subscription."
        )
    
    # Check trial expiration
    if current_user.subscription_status == SubscriptionStatus.TRIAL:
        if current_user.trial_end_date and current_user.trial_end_date <= datetime.utcnow():
            # Update user status to expired
            await firebase_manager.update_user(current_user.uid, {
                'subscription_status': SubscriptionStatus.EXPIRED.value
            })
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Trial period expired. Please subscribe to continue."
            )
    
    return current_user
