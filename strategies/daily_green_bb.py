"""
Daily Green Candle with Weekly BB Mean Reversion Strategy
==========================================================

A mean reversion strategy that identifies oversold daily candles
opening below weekly Bollinger Band 2.0 SD and exits when price returns to weekly SMA 20.

Entry Conditions (checked on completed daily bar):
1. Daily candle is GREEN (close > open)
2. Daily OPEN is below weekly BB lower band (SMA 20 ± 2.0 SD)
3. Daily body size > previous day's body size
4. Daily RSI(5) < 50 (previous day)
5. Previous day's ATR% > 3%

Entry Execution:
- Enter at OPEN of next daily candle

Exit Conditions:
- TP: Daily HIGH touches Weekly SMA 20 (BB center line)
- SL: 30% fixed stop loss from entry price

Parameters:
- BB Period: 20 (weekly SMA as center line + TP target)
- BB SD: 2.0 (sample std)
- RSI Period: 5 (daily), max 50
- ATR Period: 14 (daily), min 3%
- Stop Loss: 30%

IMPORTANT:
- This strategy internally resamples daily data to weekly
- Run on DAILY (1d) timeframe data
- Entry happens on next bar after daily signal
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from core.strategy import Strategy
from utils.indicators import RSI, ATR, BollingerBands


class DailyGreenBBStrategy(Strategy):
    """
    Daily Green Candle with Weekly BB Mean Reversion Strategy.
    
    Identifies oversold daily candles below weekly BB 2.0 SD with daily RSI < 50,
    enters next day open, exits at weekly SMA 20 touch or 30% SL.
    Uses ATR% > 3% filter to ensure sufficient volatility.
    """

    # ===== Bollinger Band Parameters (Weekly) =====
    bb_period = 20      # Weekly SMA period for BB center + TP target
    bb_sd = 1.0         # Standard deviation multiplier (sample std)

    # ===== Risk Management =====
    sl_pct = 0.30       # 30% stop loss

    # ===== RSI Filter (Daily) =====
    rsi_period = 5      # Daily RSI period
    rsi_max = 50        # Daily RSI must be below this (previous day)

    # ===== ATR Volatility Filter (Daily) =====
    atr_period = 14     # Daily ATR period
    atr_pct_min = 3.0   # Minimum ATR% required (prev day ATR/close * 100)

    # Internal state
    _weekly_data = None
    _daily_to_week_map = None

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and calculate daily and weekly indicators."""
        self.data = df.copy()
        
        # Calculate daily indicators using utils (no lookahead)
        self._calculate_daily_indicators()
        
        # Resample daily to weekly
        self._build_weekly_data()
        
        # Calculate weekly BB indicators
        self._calculate_weekly_indicators()
        
        # Map daily dates to weekly values (BB lower, SMA only)
        self._map_daily_to_weekly()
        
        # Create indicator for plotting
        close = self.data.close.values
        self.weekly_sma_daily = self.I(
            lambda: self._get_daily_sma_values(),
            name=f"Weekly SMA({self.bb_period})",
            overlay=True,
            color="blue"
        )
        
        return super().prepare(df)

    def _calculate_daily_indicators(self):
        """Calculate daily RSI and ATR% using utils.indicators (no lookahead).
        
        Daily RSI(5): Momentum oscillator (0-100)
        - Uses Wilder's smoothing (alpha=1/5)
        - < 30 oversold, > 70 overbought
        - Strategy uses < 50 filter on PREVIOUS day
        
        Daily ATR%: Volatility measure
        - ATR = Average True Range over 14 periods
        - ATR% = (ATR / close) * 100
        - Strategy requires PREVIOUS day ATR% > 3%
        
        Both indicators calculated on daily data, checked on PREVIOUS bar
        to avoid lookahead bias.
        """
        high = self.data['high'].values
        low = self.data['low'].values
        close = self.data['close'].values
        
        # Calculate daily RSI using utils (Wilder's smoothing)
        self.data['rsi'] = RSI(close, self.rsi_period)
        
        # Calculate daily ATR% using utils
        atr = ATR(high, low, close, self.atr_period)
        self.data['atr_pct'] = (atr / close) * 100

    def _build_weekly_data(self):
        """Resample daily OHLCV to weekly with Friday closes as week-end.
        
        Week definition: Monday-Friday (or first trading day to Friday)
        - Uses pandas 'W-FRI' frequency for standard market week alignment
        - OHLC aggregation:
          * open: first daily open of the week (Monday or first trading day)
          * high: maximum daily high during the week
          * low: minimum daily low during the week
          * close: last daily close of the week (Friday or last trading day)
          * volume: sum of daily volumes
        
        This ensures:
        - Consistent week boundaries aligned with market conventions
        - No lookahead bias (week ends on Friday close)
        - Accurate weekly candle representation
        """
        df = self.data.copy()
        df = df.set_index(df.index)
        
        # Resample to weekly (Friday end)
        weekly = df.resample('W-FRI').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        self._weekly_data = weekly.reset_index()
        self._weekly_data.columns = ['week_end', 'open', 'high', 'low', 'close', 'volume']

    def _calculate_weekly_indicators(self):
        """Calculate weekly Bollinger Bands using utils.indicators.
        
        Weekly Bollinger Bands (calculated on weekly resampled data):
        - Center line: 20-period Simple Moving Average (SMA)
        - Upper band: SMA + (2.0 × std)
        - Lower band: SMA - (2.0 × std)
        - Uses standard pandas rolling std (population std, ddof=1)
        
        The weekly SMA serves dual purpose:
        1. BB center line for signal detection (weekly)
        2. Take-profit target for exits (checked against daily high)
        
        No lookahead: Weekly values mapped to daily bars use merge_asof
        with direction='backward' to get most recent completed week.
        """
        close = self._weekly_data['close'].values
        
        # Calculate BB using utils function
        bb = BollingerBands(close, n=self.bb_period, std=self.bb_sd)
        
        self._weekly_data['bb_lower'] = bb['lower']
        self._weekly_data['bb_upper'] = bb['upper']
        self._weekly_data['sma'] = bb['middle']  # TP target

    def _map_daily_to_weekly(self):
        """Create mapping from daily dates to weekly BB values (lower, SMA).
        
        Uses merge_asof for O(N log W) performance instead of O(N * W) loop.
        Maps each daily bar to the most recent completed weekly bar.
        
        No lookahead bias: direction='backward' ensures we only use weekly
        data from bars that have already completed (week_end <= current_date).
        
        RSI is now calculated daily and accessed directly from self.data,
        so we only map weekly BB bands and SMA here.
        """
        weekly = self._weekly_data.copy()
        
        # Prepare daily DataFrame for merge
        daily = pd.DataFrame({'date': self.data.index}).reset_index(drop=True)
        daily['date'] = pd.to_datetime(daily['date'])
        
        # Ensure week_end is datetime for merge
        weekly['week_end'] = pd.to_datetime(weekly['week_end'])
        
        # Use merge_asof: for each daily date, find the most recent week_end <= date
        # direction='backward' means we get the week that just ended (no lookahead)
        merged = pd.merge_asof(
            daily.sort_values('date'),
            weekly[['week_end', 'bb_lower', 'sma']].sort_values('week_end'),
            left_on='date',
            right_on='week_end',
            direction='backward'
        )
        
        # Build the mapping dicts (only BB bands and SMA, not RSI)
        self._daily_to_week_map = {
            'bb_lower': dict(zip(merged['date'], merged['bb_lower'])),
            'sma': dict(zip(merged['date'], merged['sma']))
        }

    def _get_daily_sma_values(self) -> np.ndarray:
        """Get weekly SMA values mapped to daily index for plotting."""
        result = np.full(len(self.data), np.nan)
        for i, idx in enumerate(self.data.index):
            if idx in self._daily_to_week_map['sma']:
                result[i] = self._daily_to_week_map['sma'][idx]
        return result

    def on_entry(self, entry_time, entry_price, state) -> Dict[str, Any]:
        """Set stop loss at entry."""
        if entry_price is None or entry_price <= 0:
            return {}
        
        stop_loss = entry_price * (1 - self.sl_pct)
        return {"stop": stop_loss}

    def on_bar(self, ts, row, state) -> Dict[str, Any]:
        """Trading logic executed on each bar."""
        result = {
            "enter_long": False,
            "exit_long": False,
            "signal_reason": "",
        }
        
        in_position = state.get("qty", 0) > 0
        
        # ===== ENTRY LOGIC =====
        if not in_position:
            # Get weekly BB lower for current day (mapped from completed weeks only)
            weekly_bb_lower = self._daily_to_week_map['bb_lower'].get(ts)
            
            if weekly_bb_lower is None or pd.isna(weekly_bb_lower):
                return result
            
            # Get previous day's data (no lookahead - using completed bar)
            idx = self.data.index.get_loc(ts)
            if isinstance(idx, slice):
                idx = idx.start
            if idx == 0:
                return result
            
            prev_row = self.data.iloc[idx - 1]
            
            # Check entry conditions (all based on previous/current completed bars):
            # 1. Current daily candle is green
            is_green = row.close > row.open
            
            # 2. Current daily open below weekly BB lower (from completed weeks)
            opens_below_bb = row.open < weekly_bb_lower
            
            # 3. Current daily body > previous day's body
            body = abs(row.close - row.open)
            prev_body = abs(prev_row['close'] - prev_row['open'])
            bigger_body = body > prev_body
            
            # 4. Previous day's daily RSI(5) < 50 (no lookahead)
            prev_rsi = prev_row['rsi']
            rsi_ok = not pd.isna(prev_rsi) and prev_rsi < self.rsi_max
            
            # 5. Previous day's ATR% > 3% (volatility filter, no lookahead)
            prev_atr_pct = prev_row['atr_pct']
            atr_ok = not pd.isna(prev_atr_pct) and prev_atr_pct > self.atr_pct_min
            
            if is_green and opens_below_bb and bigger_body and rsi_ok and atr_ok:
                result["enter_long"] = True
                result["signal_reason"] = f"Daily Green BB (D-RSI:{prev_rsi:.1f}, ATR%:{prev_atr_pct:.2f})"
        
        # ===== EXIT LOGIC (TP check) =====
        if in_position:
            # Get weekly SMA target
            weekly_sma = self._daily_to_week_map['sma'].get(ts)
            
            if weekly_sma is not None and not np.isnan(weekly_sma):
                # Check if high touched weekly SMA
                if row.high >= weekly_sma:
                    result["exit_long"] = True
                    result["signal_reason"] = "TP: Weekly SMA Touch"
        
        return result
