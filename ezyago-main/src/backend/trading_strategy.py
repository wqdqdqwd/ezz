import pandas as pd

class TradingStrategy:
    """
    Saf EMA (9, 21) kesişimine dayalı sinyal üretici.
    """
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        print(f"Reversal Stratejisi başlatıldı: EMA({self.short_ema_period}, {self.long_ema_period})")

    def analyze_klines(self, klines: list) -> str:
        if len(klines) < self.long_ema_period:
            return "HOLD"

        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['short_ema'] = df['close'].ewm(span=self.short_ema_period, adjust=False).mean()
        df['long_ema'] = df['close'].ewm(span=self.long_ema_period, adjust=False).mean()

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        signal = "HOLD"

        if prev_row['short_ema'] < prev_row['long_ema'] and last_row['short_ema'] > last_row['long_ema']:
            signal = "LONG"
        elif prev_row['short_ema'] > prev_row['long_ema'] and last_row['short_ema'] < last_row['long_ema']:
            signal = "SHORT"
        
        return signal

trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
