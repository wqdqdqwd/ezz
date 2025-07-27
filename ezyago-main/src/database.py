import firebase_admin
from firebase_admin import credentials, db, auth
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from .config import settings
from .models import UserData, TradeData, PaymentRequest, SubscriptionStatus, BotStatus
import uuid

class FirebaseManager:
    def __init__(self):
        self.db_ref = None
        self.initialized = False
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            if not firebase_admin._apps:
                if settings.FIREBASE_CREDENTIALS_JSON and settings.FIREBASE_DATABASE_URL:
                    cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': settings.FIREBASE_DATABASE_URL
                    })
                    print("✅ Firebase Admin SDK initialized successfully")
                else:
                    raise ValueError("Firebase credentials not found in environment variables")
            
            self.db_ref = db.reference()
            self.initialized = True
            
        except Exception as e:
            print(f"❌ Firebase initialization error: {e}")
            self.initialized = False
    
    def is_ready(self) -> bool:
        return self.initialized and self.db_ref is not None
    
    # --- User Management ---
    async def create_user(self, user_data: UserData) -> bool:
        """Create a new user in the database"""
        try:
            if not self.is_ready():
                print("❌ Firebase not ready for user creation")
                return False
            
            # Check if admin user
            if user_data.email == settings.ADMIN_EMAIL:
                from .models import UserRole
                user_data.role = UserRole.ADMIN
                print(f"✅ Creating admin user: {user_data.email}")
            
            # Set trial end date
            user_data.trial_end_date = datetime.utcnow() + timedelta(days=settings.TRIAL_DAYS)
            user_data.created_at = datetime.utcnow()
            
            # Convert to dict and handle datetime serialization
            user_dict = user_data.dict()
            for key, value in user_dict.items():
                if isinstance(value, datetime):
                    user_dict[key] = value.isoformat()
            
            self.db_ref.child('users').child(user_data.uid).set(user_dict)
            print(f"✅ User {user_data.email} created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return False
    
    async def get_user(self, uid: str) -> Optional[UserData]:
        """Get user data by UID"""
        try:
            if not self.is_ready():
                return None
            
            user_ref = self.db_ref.child('users').child(uid)
            user_data = user_ref.get()
            
            if not user_data:
                return None
            
            # Convert datetime strings back to datetime objects
            for key, value in user_data.items():
                if key.endswith('_date') or key.endswith('_at') or key.endswith('_expires'):
                    if value:
                        user_data[key] = datetime.fromisoformat(value)
            
            return UserData(**user_data)
            
        except Exception as e:
            print(f"❌ Error getting user: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserData]:
        """Get user data by email"""
        try:
            if not self.is_ready():
                return None
            
            users_ref = self.db_ref.child('users')
            users_data = users_ref.order_by_child('email').equal_to(email).get()
            
            if not users_data:
                return None
            
            # Get the first (and should be only) user
            uid = list(users_data.keys())[0]
            user_data = users_data[uid]
            
            # Convert datetime strings back to datetime objects
            for key, value in user_data.items():
                if key.endswith('_date') or key.endswith('_at') or key.endswith('_expires'):
                    if value:
                        user_data[key] = datetime.fromisoformat(value)
            
            return UserData(**user_data)
            
        except Exception as e:
            print(f"❌ Error getting user by email: {e}")
            return None
    
    async def update_user(self, uid: str, updates: Dict[str, Any]) -> bool:
        """Update user data"""
        try:
            if not self.is_ready():
                return False
            
            # Handle datetime serialization
            for key, value in updates.items():
                if isinstance(value, datetime):
                    updates[key] = value.isoformat()
            
            self.db_ref.child('users').child(uid).update(updates)
            return True
            
        except Exception as e:
            print(f"❌ Error updating user: {e}")
            return False
    
    async def delete_user(self, uid: str) -> bool:
        """Delete user and all associated data"""
        try:
            if not self.is_ready():
                return False
            
            # Delete user data
            self.db_ref.child('users').child(uid).delete()
            
            # Delete user's trades
            self.db_ref.child('trades').child(uid).delete()
            
            # Delete user's payment requests
            payments_ref = self.db_ref.child('payments')
            payments = payments_ref.order_by_child('user_id').equal_to(uid).get()
            if payments:
                for payment_id in payments.keys():
                    payments_ref.child(payment_id).delete()
            
            print(f"✅ User {uid} and all associated data deleted")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting user: {e}")
            return False
    
    # --- Subscription Management ---
    async def extend_subscription(self, uid: str, days: int) -> bool:
        """Extend user subscription"""
        try:
            user = await self.get_user(uid)
            if not user:
                return False
            
            now = datetime.utcnow()
            
            # If user has active subscription, extend from current end date
            if user.subscription_end_date and user.subscription_end_date > now:
                new_end_date = user.subscription_end_date + timedelta(days=days)
            else:
                # If subscription expired or never had one, start from now
                new_end_date = now + timedelta(days=days)
            
            updates = {
                'subscription_status': SubscriptionStatus.ACTIVE.value,
                'subscription_end_date': new_end_date.isoformat()
            }
            
            return await self.update_user(uid, updates)
            
        except Exception as e:
            print(f"❌ Error extending subscription: {e}")
            return False
    
    async def check_expired_subscriptions(self) -> List[str]:
        """Check and update expired subscriptions, return list of expired user IDs"""
        try:
            if not self.is_ready():
                return []
            
            now = datetime.utcnow()
            expired_users = []
            
            users_ref = self.db_ref.child('users')
            users_data = users_ref.get()
            
            if not users_data:
                return []
            
            for uid, user_data in users_data.items():
                # Check trial expiration
                if user_data.get('subscription_status') == SubscriptionStatus.TRIAL.value:
                    trial_end = user_data.get('trial_end_date')
                    if trial_end:
                        trial_end_dt = datetime.fromisoformat(trial_end)
                        if trial_end_dt <= now:
                            await self.update_user(uid, {
                                'subscription_status': SubscriptionStatus.EXPIRED.value,
                                'bot_status': BotStatus.STOPPED.value
                            })
                            expired_users.append(uid)
                
                # Check subscription expiration
                elif user_data.get('subscription_status') == SubscriptionStatus.ACTIVE.value:
                    sub_end = user_data.get('subscription_end_date')
                    if sub_end:
                        sub_end_dt = datetime.fromisoformat(sub_end)
                        if sub_end_dt <= now:
                            await self.update_user(uid, {
                                'subscription_status': SubscriptionStatus.EXPIRED.value,
                                'bot_status': BotStatus.STOPPED.value
                            })
                            expired_users.append(uid)
            
            return expired_users
            
        except Exception as e:
            print(f"❌ Error checking expired subscriptions: {e}")
            return []
    
    # --- Trading Data ---
    async def log_trade(self, trade_data: TradeData) -> bool:
        """Log a trade to the database"""
        try:
            if not self.is_ready():
                return False
            
            trade_dict = trade_data.dict()
            for key, value in trade_dict.items():
                if isinstance(value, datetime):
                    trade_dict[key] = value.isoformat()
            
            self.db_ref.child('trades').child(trade_data.user_id).child(trade_data.trade_id).set(trade_dict)
            
            # Update user statistics
            await self._update_user_stats(trade_data.user_id, trade_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error logging trade: {e}")
            return False
    
    async def _update_user_stats(self, uid: str, trade_data: TradeData):
        """Update user trading statistics"""
        try:
            user = await self.get_user(uid)
            if not user:
                return
            
            # Only update stats when trade is closed
            if trade_data.status == "CLOSED":
                updates = {
                    'total_trades': user.total_trades + 1,
                    'total_pnl': user.total_pnl + trade_data.pnl
                }
                
                if trade_data.pnl > 0:
                    updates['winning_trades'] = user.winning_trades + 1
                else:
                    updates['losing_trades'] = user.losing_trades + 1
                
                await self.update_user(uid, updates)
                print(f"📊 User stats updated for {uid}: Total PnL: ${user.total_pnl + trade_data.pnl:.2f}")
            
        except Exception as e:
            print(f"❌ Error updating user stats: {e}")
    
    # --- Payment Management ---
    async def create_payment_request(self, payment_data: PaymentRequest) -> bool:
        """Create a payment request"""
        try:
            if not self.is_ready():
                return False
            
            payment_dict = payment_data.dict()
            for key, value in payment_dict.items():
                if isinstance(value, datetime):
                    payment_dict[key] = value.isoformat()
            
            self.db_ref.child('payments').child(payment_data.payment_id).set(payment_dict)
            return True
            
        except Exception as e:
            print(f"❌ Error creating payment request: {e}")
            return False
    
    async def get_pending_payments(self) -> List[PaymentRequest]:
        """Get all pending payment requests"""
        try:
            if not self.is_ready():
                return []
            
            payments_ref = self.db_ref.child('payments')
            payments_data = payments_ref.order_by_child('status').equal_to('pending').get()
            
            if not payments_data:
                return []
            
            payments = []
            for payment_id, payment_data in payments_data.items():
                # Convert datetime strings back to datetime objects
                for key, value in payment_data.items():
                    if key.endswith('_at'):
                        if value:
                            payment_data[key] = datetime.fromisoformat(value)
                
                payments.append(PaymentRequest(**payment_data))
            
            return payments
            
        except Exception as e:
            print(f"❌ Error getting pending payments: {e}")
            return []
    
    async def approve_payment(self, payment_id: str, admin_uid: str) -> bool:
        """Approve a payment request"""
        try:
            if not self.is_ready():
                return False
            
            # Get payment data
            payment_ref = self.db_ref.child('payments').child(payment_id)
            payment_data = payment_ref.get()
            
            if not payment_data:
                return False
            
            # Update payment status
            updates = {
                'status': 'approved',
                'processed_at': datetime.utcnow().isoformat(),
                'processed_by': admin_uid
            }
            payment_ref.update(updates)
            
            # Extend user subscription
            user_id = payment_data['user_id']
            await self.extend_subscription(user_id, settings.SUBSCRIPTION_DAYS)
            
            return True
            
        except Exception as e:
            print(f"❌ Error approving payment: {e}")
            return False
    
    # --- Admin Functions ---
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users for admin panel"""
        try:
            if not self.is_ready():
                return []
            
            users_ref = self.db_ref.child('users')
            users_data = users_ref.get()
            
            if not users_data:
                return []
            
            users = []
            for uid, user_data in users_data.items():
                # Convert datetime strings for display
                for key, value in user_data.items():
                    if key.endswith('_date') or key.endswith('_at'):
                        if value:
                            user_data[key] = datetime.fromisoformat(value)
                
                users.append(user_data)
            
            return users
            
        except Exception as e:
            print(f"❌ Error getting all users: {e}")
            return []
    
    async def get_admin_stats(self) -> Dict[str, Any]:
        """Get statistics for admin dashboard"""
        try:
            if not self.is_ready():
                return {}
            
            users_data = await self.get_all_users()
            payments_data = await self.get_pending_payments()
            
            stats = {
                'total_users': len(users_data),
                'trial_users': len([u for u in users_data if u.get('subscription_status') == 'trial']),
                'active_subscribers': len([u for u in users_data if u.get('subscription_status') == 'active']),
                'expired_users': len([u for u in users_data if u.get('subscription_status') == 'expired']),
                'pending_payments': len(payments_data),
                'active_bots': len([u for u in users_data if u.get('bot_status') == 'running']),
                'total_revenue': len([u for u in users_data if u.get('subscription_status') == 'active']) * settings.SUBSCRIPTION_PRICE_USDT
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting admin stats: {e}")
            return {}
    
    # --- IP Whitelist Management ---
    async def create_ip_whitelist_entry(self, entry: 'IPWhitelistEntry') -> bool:
        """Create IP whitelist entry"""
        try:
            if not self.is_ready():
                return False
            
            entry_dict = entry.dict()
            for key, value in entry_dict.items():
                if isinstance(value, datetime):
                    entry_dict[key] = value.isoformat()
            
            self.db_ref.child('ip_whitelist').child(entry.ip_address.replace('.', '_')).set(entry_dict)
            return True
            
        except Exception as e:
            print(f"❌ Error creating IP whitelist entry: {e}")
            return False
    
    async def get_ip_whitelist(self) -> List[Dict[str, Any]]:
        """Get all IP whitelist entries"""
        try:
            if not self.is_ready():
                return []
            
            whitelist_ref = self.db_ref.child('ip_whitelist')
            whitelist_data = whitelist_ref.get()
            
            if not whitelist_data:
                return []
            
            entries = []
            for ip_key, entry_data in whitelist_data.items():
                # Convert datetime strings back to datetime objects
                for key, value in entry_data.items():
                    if key.endswith('_at'):
                        if value:
                            entry_data[key] = datetime.fromisoformat(value)
                
                entries.append(entry_data)
            
            return entries
            
        except Exception as e:
            print(f"❌ Error getting IP whitelist: {e}")
            return []
    
    async def update_ip_whitelist_entry(self, ip_address: str, updates: Dict[str, Any]) -> bool:
        """Update IP whitelist entry"""
        try:
            if not self.is_ready():
                return False
            
            ip_key = ip_address.replace('.', '_')
            self.db_ref.child('ip_whitelist').child(ip_key).update(updates)
            return True
            
        except Exception as e:
            print(f"❌ Error updating IP whitelist entry: {e}")
            return False
    
    async def delete_ip_whitelist_entry(self, ip_address: str) -> bool:
        """Delete IP whitelist entry"""
        try:
            if not self.is_ready():
                return False
            
            ip_key = ip_address.replace('.', '_')
            self.db_ref.child('ip_whitelist').child(ip_key).delete()
            return True
            
        except Exception as e:
            print(f"❌ Error deleting IP whitelist entry: {e}")
            return False

# Global instance
firebase_manager = FirebaseManager()
