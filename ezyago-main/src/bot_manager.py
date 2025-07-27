import asyncio
import uuid
from typing import Dict, Optional
from datetime import datetime
from .models import UserData, BotStatus, TradeData
from .database import firebase_manager
from .encryption import encryption_manager
from .user_bot_instance import UserBotInstance

class BotManager:
    """
    Multi-user bot manager that handles individual bot instances for each user
    """
    def __init__(self):
        self.user_bots: Dict[str, UserBotInstance] = {}
        self.cleanup_task = None
        print("🤖 Multi-User Bot Manager initialized")
    
    async def start_user_bot(self, user: UserData, symbol: str) -> bool:
        """Start bot for a specific user"""
        try:
            # Check if user already has a running bot
            if user.uid in self.user_bots:
                existing_bot = self.user_bots[user.uid]
                if existing_bot.is_running():
                    print(f"⚠️ Bot already running for user {user.email}")
                    return False
                else:
                    # Clean up old instance
                    await existing_bot.stop()
                    del self.user_bots[user.uid]
            
            # Decrypt API credentials
            if not user.encrypted_api_key or not user.encrypted_api_secret:
                print(f"❌ No API credentials found for user {user.email}")
                return False
            
            api_key = encryption_manager.decrypt_api_key(user.encrypted_api_key)
            api_secret = encryption_manager.decrypt_api_secret(user.encrypted_api_secret)
            
            if not api_key or not api_secret:
                print(f"❌ Failed to decrypt API credentials for user {user.email}")
                return False
            
            # Prepare user settings
            user_settings = {
                'bot_order_size_usdt': user.bot_order_size_usdt,
                'bot_leverage': user.bot_leverage,
                'bot_stop_loss_percent': user.bot_stop_loss_percent,
                'bot_take_profit_percent': user.bot_take_profit_percent,
                'bot_timeframe': user.bot_timeframe
            }
            
            # Create new bot instance
            bot_instance = UserBotInstance(
                user_id=user.uid,
                user_email=user.email,
                api_key=api_key,
                api_secret=api_secret,
                is_testnet=user.is_testnet,
                user_settings=user_settings
            )
            
            # Start the bot
            success = await bot_instance.start(symbol)
            if success:
                self.user_bots[user.uid] = bot_instance
                
                # Update user status in database
                await firebase_manager.update_user(user.uid, {
                    'bot_status': BotStatus.RUNNING.value,
                    'current_symbol': symbol.upper(),
                    'bot_started_at': datetime.utcnow()
                })
                
                print(f"✅ Bot started successfully for user {user.email} with symbol {symbol}")
                return True
            else:
                print(f"❌ Failed to start bot for user {user.email}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting bot for user {user.email}: {e}")
            return False
    
    async def stop_user_bot(self, user_id: str) -> bool:
        """Stop bot for a specific user"""
        try:
            if user_id not in self.user_bots:
                print(f"⚠️ No running bot found for user {user_id}")
                return False
            
            bot_instance = self.user_bots[user_id]
            await bot_instance.stop()
            del self.user_bots[user_id]
            
            # Update user status in database
            await firebase_manager.update_user(user_id, {
                'bot_status': BotStatus.STOPPED.value,
                'current_symbol': None,
                'bot_started_at': None
            })
            
            print(f"✅ Bot stopped successfully for user {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error stopping bot for user {user_id}: {e}")
            return False
    
    async def get_user_bot_status(self, user_id: str) -> Dict:
        """Get bot status for a specific user"""
        try:
            if user_id not in self.user_bots:
                return {
                    'status': 'stopped',
                    'symbol': None,
                    'position_side': None,
                    'last_signal': None,
                    'uptime': 0,
                    'message': 'Bot is not running'
                }
            
            bot_instance = self.user_bots[user_id]
            return await bot_instance.get_status()
            
        except Exception as e:
            print(f"❌ Error getting bot status for user {user_id}: {e}")
            return {
                'status': 'error',
                'message': f'Error getting bot status: {str(e)}'
            }
    
    async def stop_all_bots(self):
        """Stop all running bots (for shutdown)"""
        print("🛑 Stopping all user bots...")
        
        for user_id, bot_instance in list(self.user_bots.items()):
            try:
                await bot_instance.stop()
                await firebase_manager.update_user(user_id, {
                    'bot_status': BotStatus.STOPPED.value,
                    'current_symbol': None,
                    'bot_started_at': None
                })
            except Exception as e:
                print(f"❌ Error stopping bot for user {user_id}: {e}")
        
        self.user_bots.clear()
        print("✅ All bots stopped")
    
    async def cleanup_inactive_bots(self):
        """Background task to cleanup inactive or errored bots"""
        while True:
            try:
                inactive_users = []
                
                for user_id, bot_instance in self.user_bots.items():
                    if not bot_instance.is_running():
                        inactive_users.append(user_id)
                
                # Clean up inactive bots
                for user_id in inactive_users:
                    print(f"🧹 Cleaning up inactive bot for user {user_id}")
                    try:
                        await self.user_bots[user_id].stop()
                        del self.user_bots[user_id]
                        
                        await firebase_manager.update_user(user_id, {
                            'bot_status': BotStatus.STOPPED.value,
                            'current_symbol': None,
                            'bot_started_at': None
                        })
                    except Exception as e:
                        print(f"❌ Error cleaning up bot for user {user_id}: {e}")
                
                # Sleep for 5 minutes before next cleanup
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"❌ Error in bot cleanup task: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute on error
    
    def get_active_bots_count(self) -> int:
        """Get number of currently active bots"""
        return len([bot for bot in self.user_bots.values() if bot.is_running()])
    
    def get_all_bot_stats(self) -> Dict:
        """Get statistics for all running bots"""
        active_bots = self.get_active_bots_count()
        total_users_with_bots = len(self.user_bots)
        
        return {
            'active_bots': active_bots,
            'total_bot_instances': total_users_with_bots,
            'bot_details': {
                user_id: {
                    'symbol': bot.current_symbol,
                    'status': 'running' if bot.is_running() else 'stopped',
                    'uptime': bot.get_uptime()
                }
                for user_id, bot in self.user_bots.items()
            }
        }

# Global bot manager instance
bot_manager = BotManager()
