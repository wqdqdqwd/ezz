import asyncio
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .config import settings

class MultiBinanceClient:
    """
    Multi-user Binance client that handles individual user API credentials
    """
    def __init__(self, api_key: str, api_secret: str, is_testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_testnet = is_testnet
        self.client: AsyncClient | None = None
        self.exchange_info = None
        
        # Use appropriate URLs based on environment
        self.base_url = settings.BINANCE_BASE_URL_TEST if is_testnet else settings.BINANCE_BASE_URL_LIVE
        self.ws_url = settings.BINANCE_WS_URL_TEST if is_testnet else settings.BINANCE_WS_URL_LIVE
        
        print(f"🔗 Binance client initialized ({'TESTNET' if is_testnet else 'LIVE'})")
    
    async def initialize(self):
        """Initialize the async client"""
        if self.client is None:
            self.client = await AsyncClient.create(
                self.api_key, 
                self.api_secret, 
                testnet=self.is_testnet
            )
            self.exchange_info = await self.client.get_exchange_info()
            print("✅ Binance AsyncClient initialized successfully")
        return self.client
    
    async def get_symbol_info(self, symbol: str):
        """Get symbol information"""
        if not self.exchange_info:
            return None
        
        for s in self.exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s
        return None
    
    async def get_open_positions(self, symbol: str):
        """Get open positions for symbol"""
        try:
            positions = await self.client.futures_position_information(symbol=symbol)
            return [p for p in positions if float(p['positionAmt']) != 0]
        except BinanceAPIException as e:
            print(f"❌ Error getting positions: {e}")
            return []
    
    async def create_market_order_with_sl(self, symbol: str, side: str, quantity: float, entry_price: float, price_precision: int, stop_loss_percent: float = 4.0):
        """Create market order with stop loss"""
        def format_price(price):
            return f"{price:.{price_precision}f}"
        
        try:
            print(f"🔄 Creating market order: {symbol} {side} {quantity}")
            
            # Create main market order
            main_order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            
            print(f"✅ Market order created: {symbol} {side} {quantity}")
            
            # Wait a bit before setting stop loss
            await asyncio.sleep(0.5)
            
            # Calculate stop loss price
            sl_price = (
                entry_price * (1 - stop_loss_percent / 100) 
                if side == 'BUY' 
                else entry_price * (1 + stop_loss_percent / 100)
            )
            
            formatted_sl_price = format_price(sl_price)
            
            # Create stop loss order
            await self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if side == 'BUY' else 'BUY',
                type='STOP_MARKET',
                stopPrice=formatted_sl_price,
                closePosition=True
            )
            
            print(f"✅ Stop loss set at {formatted_sl_price} for {symbol}")
            return main_order
            
        except BinanceAPIException as e:
            print(f"❌ Binance API Error creating order: {e}")
            error_msg = str(e)
            if "Invalid API-key" in error_msg:
                raise Exception("Geçersiz API anahtarı. Lütfen API anahtarlarınızı kontrol edin.")
            elif "Signature for this request" in error_msg:
                raise Exception("API imza hatası. API Secret'ınızı kontrol edin.")
            elif "Insufficient balance" in error_msg:
                raise Exception("Yetersiz bakiye. Hesabınızda yeterli USDT bulunmuyor.")
            else:
                raise Exception(f"Binance API hatası: {error_msg}")
            # Cancel any open orders if something went wrong
            try:
                await self.client.futures_cancel_all_open_orders(symbol=symbol)
            except:
                pass
    
    async def close_position(self, symbol: str, position_amt: float, side_to_close: str):
        """Close position"""
        try:
            # Cancel all open orders first
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            await asyncio.sleep(0.1)
            
            # Close position
            response = await self.client.futures_create_order(
                symbol=symbol,
                side=side_to_close,
                type='MARKET',
                quantity=abs(position_amt),
                reduceOnly=True
            )
            
            print(f"✅ Position closed: {symbol}")
            return response
            
        except BinanceAPIException as e:
            print(f"❌ Error closing position: {e}")
            return None
    
    async def get_last_trade_pnl(self, symbol: str) -> float:
        """Get PnL from last trade"""
        try:
            trades = await self.client.futures_account_trades(symbol=symbol, limit=5)
            if trades:
                last_order_id = trades[-1]['orderId']
                pnl = 0.0
                
                for trade in reversed(trades):
                    if trade['orderId'] == last_order_id:
                        pnl += float(trade['realizedPnl'])
                    else:
                        break
                
                return pnl
            return 0.0
            
        except BinanceAPIException as e:
            print(f"❌ Error getting trade PnL: {e}")
            return 0.0
    
    async def get_historical_klines(self, symbol: str, interval: str, limit: int = 100):
        """Get historical klines"""
        try:
            print(f"📊 Fetching {limit} historical klines for {symbol}")
            return await self.client.get_historical_klines(symbol, interval, limit=limit)
        except BinanceAPIException as e:
            print(f"❌ Error getting historical klines: {e}")
            return []
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol"""
        try:
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"✅ Leverage set to {leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            print(f"❌ Error setting leverage: {e}")
            return False
    
    async def get_market_price(self, symbol: str):
        """Get current market price"""
        try:
            ticker = await self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            print(f"❌ Error getting market price for {symbol}: {e}")
            return None
    
    async def close(self):
        """Close the client connection"""
        if self.client:
            await self.client.close_connection()
            self.client = None
            print("🔌 Binance client connection closed")