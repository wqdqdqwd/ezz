import asyncio
import json
import websockets
from datetime import datetime, timezone
from typing import Optional, Dict
import math
from .binance_client_multi import MultiBinanceClient
from .trading_strategy import trading_strategy
from .database import firebase_manager
from .models import TradeData

class UserBotInstance:
    """
    Individual bot instance for a single user
    """
    def __init__(self, user_id: str, user_email: str, api_key: str, api_secret: str, is_testnet: bool = False, user_settings: dict = None):
        self.user_id = user_id
        self.user_email = user_email
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        
        # User bot settings
        self.user_settings = user_settings or {}
        self.order_size_usdt = self.user_settings.get('bot_order_size_usdt', 25.0)
        self.leverage = self.user_settings.get('bot_leverage', 10)
        self.stop_loss_percent = self.user_settings.get('bot_stop_loss_percent', 4.0)
        self.take_profit_percent = self.user_settings.get('bot_take_profit_percent', 8.0)
        self.timeframe = self.user_settings.get('bot_timeframe', '15m')
        
        # Bot state
        self.current_symbol: Optional[str] = None
        self.position_side: Optional[str] = None
        self.last_signal: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.is_active = False
        self.stop_requested = False
        
        # Current trade tracking
        self.current_trade_id: Optional[str] = None
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None
        self.position_quantity: Optional[float] = None
        
        # Trading data
        self.klines = []
        self.quantity_precision = 0
        self.price_precision = 0
        
        # Binance client
        self.binance_client: Optional[MultiBinanceClient] = None
        
        # WebSocket connection
        self.websocket_task: Optional[asyncio.Task] = None
        
        print(f"🤖 Bot instance created for user {user_email} ({'TESTNET' if is_testnet else 'LIVE'})")
    
    async def start(self, symbol: str) -> bool:
        """Start the bot for this user"""
        try:
            if self.is_active:
                print(f"⚠️ Bot already active for user {self.user_email}")
                return False
            
            self.current_symbol = symbol.upper()
            self.stop_requested = False
            self.started_at = datetime.utcnow()
            
            print(f"🚀 Starting bot for user {self.user_email} with symbol {self.current_symbol}")
            
            # Initialize Binance client
            self.binance_client = MultiBinanceClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                is_testnet=self.is_testnet
            )
            
            try:
                await self.binance_client.initialize()
                print(f"✅ Binance client initialized for user {self.user_email}")
            except Exception as e:
                print(f"❌ Failed to initialize Binance client for user {self.user_email}: {e}")
                raise Exception("Binance bağlantısı kurulamadı. API anahtarlarınızı kontrol edin.")
            
            # Get symbol info and set precision
            symbol_info = await self.binance_client.get_symbol_info(self.current_symbol)
            if not symbol_info:
                print(f"❌ Symbol {self.current_symbol} not found for user {self.user_email}")
                raise Exception(f"Sembol {self.current_symbol} bulunamadı. Geçerli bir sembol girin.")
            
            self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
            self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
            
            # Set leverage
            if not await self.binance_client.set_leverage(self.current_symbol, self.leverage):
                print(f"❌ Failed to set leverage for user {self.user_email}")
                raise Exception("Kaldıraç ayarlanamadı. API izinlerinizi kontrol edin.")
            
            # Get historical data
            self.klines = await self.binance_client.get_historical_klines(
                self.current_symbol, 
                self.timeframe, 
                limit=50
            )
            
            if not self.klines:
                print(f"❌ Failed to get historical data for user {self.user_email}")
                raise Exception("Geçmiş veriler alınamadı. Bağlantınızı kontrol edin.")
            
            # Start WebSocket connection
            self.websocket_task = asyncio.create_task(self._websocket_handler())
            self.is_active = True
            
            print(f"✅ Bot started successfully for user {self.user_email}")
            return True
            
        except Exception as e:
            print(f"❌ Error starting bot for user {self.user_email}: {e}")
            await self._cleanup()
    
    async def stop(self):
        """Stop the bot for this user"""
        try:
            print(f"🛑 Stopping bot for user {self.user_email}")
            
            self.stop_requested = True
            self.is_active = False
            
            # Cancel WebSocket task
            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
            
            await self._cleanup()
            print(f"✅ Bot stopped for user {self.user_email}")
            
        except Exception as e:
            print(f"❌ Error stopping bot for user {self.user_email}: {e}")
    
    async def _cleanup(self):
        """Clean up resources"""
        if self.binance_client:
            await self.binance_client.close()
            self.binance_client = None
        
        self.websocket_task = None
        self.is_active = False
    
    async def _websocket_handler(self):
        """Handle WebSocket connection for real-time data"""
        from .config import settings
        ws_url = f"{settings.BINANCE_WS_URL_LIVE if not self.is_testnet else settings.BINANCE_WS_URL_TEST}/ws/{self.current_symbol.lower()}@kline_{self.timeframe}"
        
        while not self.stop_requested:
            try:
                print(f"🔌 Connecting to WebSocket for user {self.user_email}: {ws_url}")
                
                async with websockets.connect(ws_url, ping_interval=30, ping_timeout=15) as ws:
                    print(f"✅ WebSocket connected for user {self.user_email}")
                    
                    while not self.stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                            await self._handle_websocket_message(message)
                            
                        except asyncio.TimeoutError:
                            print(f"⚠️ WebSocket timeout for user {self.user_email}")
                            break
                        except websockets.exceptions.ConnectionClosed:
                            print(f"⚠️ WebSocket connection closed for user {self.user_email}")
                            break
                            
            except Exception as e:
                if not self.stop_requested:
                    print(f"❌ WebSocket error for user {self.user_email}: {e}")
                    await asyncio.sleep(5)  # Wait before reconnecting
                else:
                    break
    
    async def _handle_websocket_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Only process closed candles
            if not data.get('k', {}).get('x', False):
                return
            
            kline = data['k']
            print(f"📊 New candle closed for {self.user_email}: {self.current_symbol} - Close: {kline['c']}")
            
            # Update klines data
            self.klines.pop(0)
            self.klines.append([
                kline['t'], kline['o'], kline['h'], kline['l'], 
                kline['c'], kline['v'], kline['T'], kline['q'], 
                kline['n'], kline['V'], kline['Q'], '0'
            ])
            
            # Check current position
            open_positions = await self.binance_client.get_open_positions(self.current_symbol)
            
            # Check if position was closed by stop loss or take profit
            if self.position_side is not None and not open_positions:
                print(f"🛑 Position closed automatically for user {self.user_email}")
                await self._log_trade_closure("CLOSED_BY_SL_OR_TP")
                self.position_side = None
                self.current_trade_id = None
                self.entry_price = None
                self.entry_time = None
                self.position_quantity = None
            
            # Check for take profit if position is open
            elif self.position_side is not None and open_positions:
                await self._check_take_profit(open_positions[0])
            
            # Get new signal
            signal = trading_strategy.analyze_klines(self.klines)
            self.last_signal = signal
            
            print(f"📈 Signal for {self.user_email}: {signal}")
            
            # Execute trade if signal changed
            if signal != "HOLD" and signal != self.position_side:
                await self._execute_trade(signal)
                
        except Exception as e:
            print(f"❌ Error handling WebSocket message for user {self.user_email}: {e}")
    
    async def _execute_trade(self, new_signal: str):
        """Execute trade based on new signal"""
        try:
            print(f"🔄 Executing trade for user {self.user_email}: {new_signal}")
            
            # Close existing position if any
            open_positions = await self.binance_client.get_open_positions(self.current_symbol)
            if open_positions:
                position = open_positions[0]
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                
                print(f"📤 Closing existing position for user {self.user_email}")
                await self._log_trade_closure("CLOSED_BY_FLIP")
                await self.binance_client.close_position(self.current_symbol, position_amt, side_to_close)
                await asyncio.sleep(1)  # Wait for position to close
            
            # Open new position
            side = "BUY" if new_signal == "LONG" else "SELL"
            price = await self.binance_client.get_market_price(self.current_symbol)
            
            if not price:
                print(f"❌ Failed to get market price for user {self.user_email}")
                return
            
            quantity = self._format_quantity((self.order_size_usdt * self.leverage) / price)
            
            if quantity <= 0:
                print(f"❌ Invalid quantity calculated for user {self.user_email}")
                return
            
            # Create market order with stop loss (take profit will be monitored separately)
            order = await self.binance_client.create_market_order_with_sl(
                self.current_symbol, side, quantity, price, self.price_precision, self.stop_loss_percent
            )
            
            if order:
                self.position_side = new_signal
                self.entry_price = price
                self.entry_time = datetime.utcnow()
                self.position_quantity = quantity
                print(f"✅ New {new_signal} position opened for user {self.user_email} at {price}")
                
                # Log trade opening
                await self._log_trade_opening(new_signal, price, quantity)
            else:
                print(f"❌ Failed to open position for user {self.user_email}")
                self.position_side = None
                
        except Exception as e:
            print(f"❌ Error executing trade for user {self.user_email}: {e}")
    
    async def _check_take_profit(self, position):
        """Check if take profit target is reached"""
        try:
            if not self.entry_price or not self.position_side:
                return
            
            current_price = await self.binance_client.get_market_price(self.current_symbol)
            if not current_price:
                return
            
            # Calculate profit percentage
            if self.position_side == "LONG":
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # SHORT
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
            print(f"📊 Current profit for {self.user_email}: {profit_percent:.2f}% (Target: {self.take_profit_percent}%)")
            
            # Check if take profit target is reached
            if profit_percent >= self.take_profit_percent:
                print(f"🎯 Take profit target reached for user {self.user_email}! Closing position...")
                
                # Close position
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                
                await self.binance_client.close_position(self.current_symbol, position_amt, side_to_close)
                
                # Log trade closure
                await self._log_trade_closure("CLOSED_BY_TAKE_PROFIT")
                
                # Reset position tracking
                self.position_side = None
                self.current_trade_id = None
                self.entry_price = None
                self.entry_time = None
                self.position_quantity = None
                
        except Exception as e:
            print(f"❌ Error checking take profit for user {self.user_email}: {e}")
    
    async def _log_trade_opening(self, side: str, entry_price: float, quantity: float):
        """Log trade opening"""
        try:
            self.current_trade_id = f"{self.user_id}_{int(datetime.utcnow().timestamp())}"
            
            trade_data = TradeData(
                trade_id=self.current_trade_id,
                user_id=self.user_id,
                symbol=self.current_symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                pnl=0.0,
                status="OPEN",
                entry_time=datetime.utcnow(),
                close_reason=""
            )
            
            await firebase_manager.log_trade(trade_data)
            print(f"📝 Trade opening logged for user {self.user_email}: {self.current_trade_id}")
            
        except Exception as e:
            print(f"❌ Error logging trade opening for user {self.user_email}: {e}")
    
    async def _log_trade_closure(self, close_reason: str):
        """Log trade closure"""
        try:
            pnl = await self.binance_client.get_last_trade_pnl(self.current_symbol)
            current_price = await self.binance_client.get_market_price(self.current_symbol)
            
            # Create trade closure log
            trade_data = TradeData(
                trade_id=self.current_trade_id or f"{self.user_id}_{int(datetime.utcnow().timestamp())}",
                user_id=self.user_id,
                symbol=self.current_symbol,
                side=self.position_side or "UNKNOWN",
                entry_price=self.entry_price or 0.0,
                exit_price=current_price,
                quantity=self.position_quantity or 0.0,
                pnl=pnl,
                status="CLOSED",
                entry_time=self.entry_time or datetime.utcnow(),
                exit_time=datetime.utcnow(),
                close_reason=close_reason
            )
            
            await firebase_manager.log_trade(trade_data)
            print(f"📝 Trade closure logged for user {self.user_email}: PnL ${pnl:.2f}")
            
        except Exception as e:
            print(f"❌ Error logging trade closure for user {self.user_email}: {e}")
    
    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        """Get precision from symbol filter"""
        for f in symbol_info['filters']:
            if f['filterType'] == filter_type:
                size_str = f[key]
                if '.' in size_str:
                    return len(size_str.split('.')[1].rstrip('0'))
                return 0
        return 0
    
    def _format_quantity(self, quantity: float):
        """Format quantity according to precision"""
        if self.quantity_precision == 0:
            return math.floor(quantity)
        factor = 10 ** self.quantity_precision
        return math.floor(quantity * factor) / factor
    
    def is_running(self) -> bool:
        """Check if bot is currently running"""
        return self.is_active and not self.stop_requested
    
    def get_uptime(self) -> int:
        """Get bot uptime in seconds"""
        if not self.started_at:
            return 0
        return int((datetime.utcnow() - self.started_at).total_seconds())
    
    async def get_status(self) -> Dict:
        """Get current bot status"""
        return {
            'status': 'running' if self.is_running() else 'stopped',
            'symbol': self.current_symbol,
            'position_side': self.position_side,
            'last_signal': self.last_signal,
            'uptime': self.get_uptime(),
            'message': f"Bot is {'running' if self.is_running() else 'stopped'} for {self.current_symbol}"
        }