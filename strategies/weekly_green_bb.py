"""
Weekly Green Candle Mean Reversion Strategy
============================================

A mean reversion strategy that identifies oversold weekly candles
opening below Bollinger Band 2.0 SD and exits when price returns to EMA 20.

Entry Conditions (checked on completed weekly bar):
1. Weekly candle is GREEN (close > open)
2. Weekly OPEN is below BB lower band (SMA 20 ± 2.0 SD)
3. Weekly body size > previous week's body size
4. Weekly RSI(14) < 60 on signal week

Entry Execution:
- Enter at OPEN of first trading day after signal week (Monday)

Exit Conditions:
- TP: Daily HIGH touches Weekly SMA 20 (BB center line)
- SL: 30% fixed stop loss from entry price

Parameters:
- BB Period: 20 (weekly SMA as center line + TP target)
- BB SD: 2.0 (sample std to match TradingView)
- RSI Period: 14 (weekly), max 60
- Stop Loss: 30%

IMPORTANT:
- This strategy internally resamples daily data to weekly
- Best run on DAILY (1d) timeframe data
- Entry happens on next bar after weekly signal
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from core.strategy import Strategy


class WeeklyGreenBBStrategy(Strategy):
    """
    Weekly Green Candle Mean Reversion Strategy.
    
    Identifies oversold weekly candles below BB 2.0 SD,
    enters on Monday open, exits at EMA 20 touch or 30% SL.
    """

    # ===== Bollinger Band Parameters =====
    bb_period = 20      # Weekly SMA period for BB center + TP target
    bb_sd = 2.0         # Standard deviation multiplier (sample std)

    # ===== Risk Management =====
    sl_pct = 0.30       # 30% stop loss

    # ===== RSI Filter =====
    rsi_period = 14     # Weekly RSI period
    rsi_max = 60        # Weekly RSI must be below this on signal week

    # Internal state
    _weekly_data = None
    _weekly_rsi = None
    _daily_to_week_map = None
    _signal_bar_dates = None

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and calculate weekly indicators."""
        self.data = df.copy()
        
        # Resample daily to weekly
        self._build_weekly_data()
        
        # Calculate weekly RSI for filtering
        self._calculate_weekly_rsi()
        
        # Calculate weekly indicators
        self._calculate_weekly_indicators()
        
        # Identify signal bars (now includes RSI filter)
        self._find_signal_bars()
        
        # Map daily dates to their weekly SMA values (TP target)
        self._map_daily_to_weekly_sma()
        
        # Create dummy indicator for plotting (using daily close as proxy)
        close = self.data.close.values
        self.weekly_sma_daily = self.I(
            lambda: self._get_daily_sma_values(),
            name=f"Weekly SMA({self.bb_period})",
            overlay=True,
            color="blue"
        )
        
        return super().prepare(df)

    def _calculate_weekly_rsi(self):
        """Calculate weekly RSI for filtering."""
        close = self._weekly_data['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.ewm(alpha=1/self.rsi_period, min_periods=self.rsi_period).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, min_periods=self.rsi_period).mean()
        
        rs = avg_gain / avg_loss
        self._weekly_data['rsi'] = 100 - (100 / (1 + rs))

    def _build_weekly_data(self):
        """Resample daily OHLCV to weekly."""
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
        """Calculate BB (SMA-based) on weekly data. SMA is used for both BB center and TP target."""
        close = self._weekly_data['close'].values
        
        # SMA for BB center and TP target
        sma = pd.Series(close).rolling(self.bb_period).mean().values
        std = pd.Series(close).rolling(self.bb_period).std(ddof=1).values
        self._weekly_data['bb_lower'] = sma - self.bb_sd * std
        self._weekly_data['sma'] = sma  # TP target

    def _find_signal_bars(self):
        """Identify weeks with valid entry signals."""
        self._signal_bar_dates = set()
        
        weekly = self._weekly_data
        
        for i in range(2, len(weekly)):
            row = weekly.iloc[i]
            prev_row = weekly.iloc[i - 1]
            
            # Check conditions
            bb_lower = row['bb_lower']
            if pd.isna(bb_lower):
                continue
            
            is_green = row['close'] > row['open']
            opens_below_bb = row['open'] < bb_lower
            body = abs(row['close'] - row['open'])
            prev_body = abs(prev_row['close'] - prev_row['open'])
            bigger_body = body > prev_body
            
            if is_green and opens_below_bb and bigger_body:
                # RSI Filter: Check weekly RSI on signal week
                weekly_rsi = row.get('rsi', np.nan)
                
                # Weekly RSI must be below threshold
                if pd.isna(weekly_rsi) or weekly_rsi >= self.rsi_max:
                    continue
                
                # Signal detected - mark the week end date
                self._signal_bar_dates.add(row['week_end'])

    def _map_daily_to_weekly_sma(self):
        """Create mapping from daily dates to previous week's SMA (TP target).
        
        Uses merge_asof for O(N log W) performance instead of O(N * W) loop.
        """
        weekly = self._weekly_data.copy()
        
        # Shift SMA by 1 week to get previous week's value (avoid look-ahead)
        weekly['prev_sma'] = weekly['sma'].shift(1)
        
        # Prepare daily DataFrame for merge
        daily = pd.DataFrame({'date': self.data.index}).reset_index(drop=True)
        daily['date'] = pd.to_datetime(daily['date'])
        
        # Ensure week_end is datetime for merge
        weekly['week_end'] = pd.to_datetime(weekly['week_end'])
        
        # Use merge_asof: for each daily date, find the most recent week_end <= date
        # direction='backward' means we get the week that just ended
        merged = pd.merge_asof(
            daily.sort_values('date'),
            weekly[['week_end', 'prev_sma']].sort_values('week_end'),
            left_on='date',
            right_on='week_end',
            direction='backward'
        )
        
        # Build the mapping dict
        self._daily_to_week_map = dict(zip(merged['date'], merged['prev_sma']))

    def _get_daily_sma_values(self) -> np.ndarray:
        """Get weekly SMA values mapped to daily index for plotting."""
        result = np.full(len(self.data), np.nan)
        for i, idx in enumerate(self.data.index):
            if idx in self._daily_to_week_map:
                result[i] = self._daily_to_week_map[idx]
        return result

    def _get_week_end_for_date(self, date) -> Optional[pd.Timestamp]:
        """Get the week end date (Friday) for a given date."""
        weekly = self._weekly_data
        week_mask = weekly['week_end'] >= date
        if week_mask.any():
            return weekly[week_mask].iloc[0]['week_end']
        return None

    def _was_signal_previous_week(self, current_date) -> bool:
        """Check if previous week had a signal."""
        weekly = self._weekly_data
        
        # Find current week
        week_mask = weekly['week_end'] >= current_date
        if not week_mask.any():
            return False
        
        current_week_idx = weekly[week_mask].index[0]
        
        # Check if previous week was a signal
        if current_week_idx > 0:
            prev_week_end = weekly.iloc[current_week_idx - 1]['week_end']
            return prev_week_end in self._signal_bar_dates
        
        return False

    def _is_first_day_of_week(self, current_date) -> bool:
        """Check if this is the first trading day of the week."""
        # Get previous trading day
        try:
            idx = self.data.index.get_loc(current_date)
            # Handle case where get_loc returns a slice (duplicate dates)
            if isinstance(idx, slice):
                idx = idx.start
            if idx == 0:
                return True
            
            prev_date = self.data.index[idx - 1]
            
            # Check if previous day was in a different week
            current_week = self._get_week_end_for_date(current_date)
            prev_week = self._get_week_end_for_date(prev_date)
            
            return current_week != prev_week
        except (KeyError, TypeError):
            return False

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
            # Check if this is first day of week and previous week had signal
            if self._is_first_day_of_week(ts) and self._was_signal_previous_week(ts):
                result["enter_long"] = True
                result["signal_reason"] = "Weekly Green BB Signal"
        
        # ===== EXIT LOGIC (TP check) =====
        if in_position:
            # Get current week's SMA target (use previous week's value)
            weekly_sma = self._daily_to_week_map.get(ts)
            
            if weekly_sma is not None and not np.isnan(weekly_sma):
                # Check if high touched SMA
                if row.high >= weekly_sma:
                    result["exit_long"] = True
                    result["signal_reason"] = "TP: SMA Touch"
        
        return result
