class TradingStrategy:
    """
    EMA (9,21) crossover strategy without pandas dependency
    """
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        print(f"✅ Trading Strategy initialized: EMA({self.short_ema_period}, {self.long_ema_period})")

    def analyze_klines(self, klines: list) -> str:
        """Analyze klines and return trading signal"""
        if len(klines) < self.long_ema_period:
            return "HOLD"

        # Extract close prices
        close_prices = [float(kline[4]) for kline in klines]
        
        # Calculate EMAs manually
        short_ema = self._calculate_ema(close_prices, self.short_ema_period)
        long_ema = self._calculate_ema(close_prices, self.long_ema_period)
        
        # Get last two EMA values
        current_short = short_ema[-1]
        current_long = long_ema[-1]
        prev_short = short_ema[-2]
        prev_long = long_ema[-2]
        
        signal = "HOLD"

        # Check for EMA crossover
        if prev_short < prev_long and current_short > current_long:
            signal = "LONG"
        elif prev_short > prev_long and current_short < current_long:
            signal = "SHORT"
        
        return signal
    
    def _calculate_ema(self, prices: list, period: int) -> list:
        """Calculate EMA manually without pandas"""
        if len(prices) < period:
            return prices
        
        ema_values = []
        multiplier = 2 / (period + 1)
        
        # Start with SMA for first value
        sma = sum(prices[:period]) / period
        ema_values.append(sma)
        
        # Calculate EMA for remaining values
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)
        
        # Pad the beginning with the first EMA value
        result = [ema_values[0]] * (period - 1) + ema_values
        return result

# Global instance
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)