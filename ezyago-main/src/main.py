import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uuid

# Import our modules
from .config import settings
from .database import firebase_manager
from .auth import auth_manager, get_current_user, get_current_admin, get_active_user
from .models import *
from .middleware import SecurityMiddleware, LoggingMiddleware, ErrorHandlerMiddleware
from .rate_limiter import start_rate_limiter_cleanup
from .encryption import encryption_manager
from .bot_manager import bot_manager

# Background tasks
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    print("🚀 Starting Ezyago Multi-User Trading Bot Platform...")
    
    # Startup validation
    startup_checks = {
        "Firebase": firebase_manager.is_ready(),
        "Encryption": encryption_manager.is_ready(),
    }
    
    print("🔍 Startup Checks:")
    for service, status in startup_checks.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {service}: {'Ready' if status else 'Not Ready'}")
    
    # Start background tasks
    print("🔄 Starting background tasks...")
    background_tasks.append(asyncio.create_task(start_rate_limiter_cleanup()))
    background_tasks.append(asyncio.create_task(bot_manager.cleanup_inactive_bots()))
    
    yield
    
    # Cleanup
    print("🛑 Shutting down...")
    await bot_manager.stop_all_bots()
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

# Create FastAPI app
app = FastAPI(
    title="Ezyago Trading Bot Platform",
    description="Multi-user automated trading bot platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityMiddleware)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "firebase": firebase_manager.is_ready(),
            "encryption": encryption_manager.is_ready()
        }
    }

# Authentication endpoints
@app.post("/api/auth/register")
async def register_user(user_data: UserRegister):
    """Register a new user"""
    try:
        print(f"🔄 Registration attempt for: {user_data.email}")
        
        # Validate input
        if not user_data.email or not user_data.password or not user_data.full_name:
            print(f"❌ Missing required fields for: {user_data.email}")
            raise HTTPException(
                status_code=400,
                detail="Tüm alanlar gereklidir"
            )
        
        if len(user_data.password) < 6:
            print(f"❌ Password too short for: {user_data.email}")
            raise HTTPException(
                status_code=400,
                detail="Şifre en az 6 karakter olmalıdır"
            )
        
        # Register user
        user = await auth_manager.register_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )
        
        if not user:
            print(f"❌ Registration failed for: {user_data.email}")
            raise HTTPException(
                status_code=400,
                detail="Bu e-posta adresi zaten kullanılıyor"
            )
        
        # Create access token
        access_token = auth_manager.create_access_token(
            data={"sub": user.uid, "email": user.email}
        )
        
        print(f"✅ Registration successful for: {user_data.email}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "uid": user.uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "subscription_status": user.subscription_status,
                "trial_end_date": user.trial_end_date.isoformat() if user.trial_end_date else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error for {user_data.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Kayıt işlemi sırasında hata oluştu"
        )

@app.post("/api/auth/login")
async def login_user(user_data: UserLogin):
    """Login user"""
    try:
        print(f"🔄 Login attempt for: {user_data.email}")
        
        # Validate input
        if not user_data.email or not user_data.password:
            print(f"❌ Missing credentials for: {user_data.email}")
            raise HTTPException(
                status_code=400,
                detail="E-posta ve şifre gereklidir"
            )
        
        # Authenticate user
        user = await auth_manager.authenticate_user(
            email=user_data.email,
            password=user_data.password
        )
        
        if not user:
            print(f"❌ Authentication failed for: {user_data.email}")
            raise HTTPException(
                status_code=401,
                detail="E-posta veya şifre hatalı"
            )
        
        # Check if user is blocked
        if user.is_blocked:
            print(f"❌ Blocked user login attempt: {user_data.email}")
            raise HTTPException(
                status_code=403,
                detail="Hesabınız engellenmiş. Lütfen destek ile iletişime geçin."
            )
        
        # Create access token
        access_token = auth_manager.create_access_token(
            data={"sub": user.uid, "email": user.email}
        )
        
        print(f"✅ Login successful for: {user_data.email} (Role: {user.role})")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "uid": user.uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "subscription_status": user.subscription_status,
                "trial_end_date": user.trial_end_date.isoformat() if user.trial_end_date else None,
                "subscription_end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error for {user_data.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Giriş işlemi sırasında hata oluştu"
        )

# User profile endpoints
@app.get("/api/user/profile")
async def get_user_profile(current_user: UserData = Depends(get_current_user)):
    """Get current user profile"""
    try:
        print(f"📊 Profile request from: {current_user.email}")
        
        return {
            "uid": current_user.uid,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "subscription_status": current_user.subscription_status,
            "trial_end_date": current_user.trial_end_date.isoformat() if current_user.trial_end_date else None,
            "subscription_end_date": current_user.subscription_end_date.isoformat() if current_user.subscription_end_date else None,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "email_verified": current_user.email_verified,
            "language": current_user.language
        }
        
    except Exception as e:
        print(f"❌ Profile error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Profil bilgileri alınırken hata oluştu"
        )

@app.put("/api/user/profile")
async def update_user_profile(profile_data: dict, current_user: UserData = Depends(get_current_user)):
    """Update user profile"""
    try:
        print(f"🔄 Profile update for: {current_user.email}")
        
        # Update user profile
        updates = {}
        if "full_name" in profile_data:
            updates["full_name"] = profile_data["full_name"]
        if "language" in profile_data:
            updates["language"] = profile_data["language"]
        
        if updates:
            await firebase_manager.update_user(current_user.uid, updates)
            print(f"✅ Profile updated for: {current_user.email}")
        
        return {"message": "Profil başarıyla güncellendi"}
        
    except Exception as e:
        print(f"❌ Profile update error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Profil güncellenirken hata oluştu"
        )

# API Keys endpoints
@app.post("/api/user/api-keys")
async def save_api_keys(api_data: APIKeysUpdate, current_user: UserData = Depends(get_current_user)):
    """Save user API keys"""
    try:
        print(f"🔄 API keys update for: {current_user.email}")
        
        # Encrypt API keys
        encrypted_key = encryption_manager.encrypt_api_key(api_data.api_key)
        encrypted_secret = encryption_manager.encrypt_api_secret(api_data.api_secret)
        
        if not encrypted_key or not encrypted_secret:
            print(f"❌ Encryption failed for: {current_user.email}")
            raise HTTPException(
                status_code=500,
                detail="API anahtarları şifrelenirken hata oluştu"
            )
        
        # Update user
        await firebase_manager.update_user(current_user.uid, {
            "encrypted_api_key": encrypted_key,
            "encrypted_api_secret": encrypted_secret,
            "is_testnet": api_data.is_testnet
        })
        
        print(f"✅ API keys saved for: {current_user.email}")
        return {"message": "API anahtarları başarıyla kaydedildi"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API keys save error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="API anahtarları kaydedilirken hata oluştu"
        )

@app.delete("/api/user/api-keys")
async def delete_api_keys(current_user: UserData = Depends(get_current_user)):
    """Delete user API keys"""
    try:
        print(f"🔄 API keys deletion for: {current_user.email}")
        
        await firebase_manager.update_user(current_user.uid, {
            "encrypted_api_key": None,
            "encrypted_api_secret": None,
            "is_testnet": False
        })
        
        print(f"✅ API keys deleted for: {current_user.email}")
        return {"message": "API anahtarları silindi"}
        
    except Exception as e:
        print(f"❌ API keys deletion error for {current_user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="API anahtarları silinirken hata oluştu"
        )

# Bot control endpoints
@app.post("/api/bot/start")
async def start_bot(request: BotControl, current_user: UserData = Depends(get_active_user)):
    """Start bot for authenticated user"""
    try:
        print(f"🔄 Bot start request from user: {current_user.email}")
        print(f"📊 Request data: action={request.action}, symbol={request.symbol}")
        
        # Validate symbol
        if not request.symbol:
            print(f"❌ No symbol provided by user: {current_user.email}")
            raise HTTPException(status_code=400, detail="Symbol gereklidir")
        
        symbol = request.symbol.upper()
        print(f"📊 Processing symbol: {symbol} for user: {current_user.email}")
        
        # Check if user has API keys
        if not current_user.encrypted_api_key or not current_user.encrypted_api_secret:
            print(f"❌ User {current_user.email} has no API keys configured")
            raise HTTPException(
                status_code=400, 
                detail="Önce API anahtarlarınızı kaydetmelisiniz. Ayarlar > API Anahtarları bölümünden ekleyebilirsiniz."
            )
        
        # Check if bot is already running
        if current_user.bot_status == BotStatus.RUNNING:
            print(f"⚠️ Bot already running for user: {current_user.email}")
            raise HTTPException(
                status_code=400,
                detail="Bot zaten çalışıyor. Önce durdurun, sonra yeni sembol ile başlatın."
            )
        
        print(f"✅ All checks passed for user: {current_user.email}, starting bot...")
        
        # Start bot using bot manager
        success = await bot_manager.start_user_bot(current_user, symbol)
        
        if not success:
            print(f"❌ Failed to start bot for user: {current_user.email}")
            raise HTTPException(
                status_code=500,
                detail="Bot başlatılamadı. API anahtarlarınızı kontrol edin."
            )
        
        success_message = f"Bot {symbol} sembolü için başarıyla başlatıldı!"
        print(f"✅ Bot started successfully for user {current_user.email}: {success_message}")
        
        return {
            "success": True,
            "message": success_message,
            "status": "running",
            "symbol": symbol
        }
            
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Bot başlatılırken beklenmeyen hata: {str(e)}"
        print(f"❌ Unexpected error starting bot for user {current_user.email}: {error_message}")
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/api/bot/stop")
async def stop_bot(current_user: UserData = Depends(get_current_user)):
    """Stop bot for authenticated user"""
    try:
        print(f"🔄 Bot stop request from user: {current_user.email}")
        
        if current_user.bot_status != BotStatus.RUNNING:
            print(f"⚠️ Bot not running for user: {current_user.email}")
            raise HTTPException(status_code=400, detail="Bot zaten durdurulmuş")
        
        # Stop bot using bot manager
        success = await bot_manager.stop_user_bot(current_user.uid)
        
        if not success:
            print(f"❌ Failed to stop bot for user: {current_user.email}")
            raise HTTPException(status_code=500, detail="Bot durdurulamadı")
        
        success_message = "Bot başarıyla durduruldu"
        print(f"✅ Bot stopped for user: {current_user.email}")
        
        return {
            "success": True,
            "message": success_message,
            "status": "stopped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Bot stop error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Bot durdurulurken hata oluştu")

@app.get("/api/bot/status")
async def get_bot_status(current_user: UserData = Depends(get_current_user)):
    """Get bot status for authenticated user"""
    try:
        # Get bot status from bot manager
        bot_status = await bot_manager.get_user_bot_status(current_user.uid)
        
        # Get fresh user data for stats
        fresh_user = await firebase_manager.get_user(current_user.uid) or current_user
        
        # Merge bot status with user stats
        return {
            **bot_status,
            "total_trades": fresh_user.total_trades,
            "winning_trades": fresh_user.winning_trades,
            "losing_trades": fresh_user.losing_trades,
            "total_pnl": fresh_user.total_pnl
        }
        
    except Exception as e:
        print(f"❌ Bot status error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Bot durumu alınırken hata oluştu")

@app.get("/api/bot/settings")
async def get_bot_settings(current_user: UserData = Depends(get_current_user)):
    """Get bot settings for authenticated user"""
    try:
        return {
            "order_size_usdt": current_user.bot_order_size_usdt,
            "leverage": current_user.bot_leverage,
            "stop_loss_percent": current_user.bot_stop_loss_percent,
            "take_profit_percent": current_user.bot_take_profit_percent,
            "timeframe": current_user.bot_timeframe
        }
        
    except Exception as e:
        print(f"❌ Bot settings error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Bot ayarları alınırken hata oluştu")

@app.post("/api/bot/settings")
async def update_bot_settings(settings_data: BotSettings, current_user: UserData = Depends(get_current_user)):
    """Update bot settings for authenticated user"""
    try:
        print(f"🔄 Bot settings update for: {current_user.email}")
        
        # Update settings
        await firebase_manager.update_user(current_user.uid, {
            "bot_order_size_usdt": settings_data.order_size_usdt,
            "bot_leverage": settings_data.leverage,
            "bot_stop_loss_percent": settings_data.stop_loss_percent,
            "bot_take_profit_percent": settings_data.take_profit_percent,
            "bot_timeframe": settings_data.timeframe
        })
        
        print(f"✅ Bot settings updated for: {current_user.email}")
        return {"message": "Bot ayarları başarıyla güncellendi"}
        
    except Exception as e:
        print(f"❌ Bot settings update error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Bot ayarları güncellenirken hata oluştu")

# Payment endpoints
@app.get("/api/payment/wallet")
async def get_wallet_info(current_user: UserData = Depends(get_current_user)):
    """Get wallet information"""
    try:
        return {
            "wallet_address": settings.USDT_WALLET_ADDRESS,
            "amount": settings.SUBSCRIPTION_PRICE_USDT,
            "currency": "USDT"
        }
        
    except Exception as e:
        print(f"❌ Wallet info error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Cüzdan bilgileri alınırken hata oluştu")

@app.post("/api/payment/request")
async def request_payment(payment_data: PaymentNotification, current_user: UserData = Depends(get_current_user)):
    """Request payment notification"""
    try:
        print(f"🔄 Payment request from: {current_user.email}")
        
        # Create payment request
        payment_request = PaymentRequest(
            payment_id=str(uuid.uuid4()),
            user_id=current_user.uid,
            user_email=current_user.email,
            amount=settings.SUBSCRIPTION_PRICE_USDT,
            message=payment_data.message,
            created_at=datetime.utcnow()
        )
        
        await firebase_manager.create_payment_request(payment_request)
        
        print(f"✅ Payment request created for: {current_user.email}")
        return {"message": "Ödeme bildirimi gönderildi. 24 saat içinde onaylanacaktır."}
        
    except Exception as e:
        print(f"❌ Payment request error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Ödeme bildirimi gönderilirken hata oluştu")

# Admin endpoints
@app.get("/api/admin/stats")
async def get_admin_stats(current_admin: UserData = Depends(get_current_admin)):
    """Get admin statistics"""
    try:
        stats = await firebase_manager.get_admin_stats()
        return stats
        
    except Exception as e:
        print(f"❌ Admin stats error: {e}")
        raise HTTPException(status_code=500, detail="İstatistikler alınırken hata oluştu")

# Account deletion
@app.delete("/api/user/account")
async def delete_account(current_user: UserData = Depends(get_current_user)):
    """Delete user account"""
    try:
        print(f"🔄 Account deletion for: {current_user.email}")
        
        await firebase_manager.delete_user(current_user.uid)
        
        print(f"✅ Account deleted for: {current_user.email}")
        return {"message": "Hesabınız başarıyla silindi"}
        
    except Exception as e:
        print(f"❌ Account deletion error for {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Hesap silinirken hata oluştu")

# Static files and routes
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/admin")
async def admin_panel():
    """Admin panel page"""
    return FileResponse('static/admin.html')

@app.get("/api-guide")
async def api_guide():
    """API guide page"""
    return FileResponse('static/api-guide.html')

@app.get("/about")
async def about_page():
    """About page"""
    return FileResponse('static/about.html')

@app.get("/contact")
async def contact_page():
    """Contact page"""
    return FileResponse('static/contact.html')

@app.get("/privacy")
async def privacy_page():
    """Privacy policy page"""
    return FileResponse('static/privacy.html')

@app.get("/terms")
async def terms_page():
    """Terms of service page"""
    return FileResponse('static/terms.html')

@app.get("/risk")
async def risk_page():
    """Risk disclosure page"""
    return FileResponse('static/risk.html')

@app.get("/")
async def read_index():
    """Main page"""
    return FileResponse('static/index.html')
