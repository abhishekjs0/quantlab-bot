"""
TEMA-LSMA Crossover Strategy
============================

Clean crossover strategy combining TEMA (Triple EMA) and LSMA (Linear Regression)
for trend detection with multi-level take profits.

Converted from TradingView Pine Script v6.

Entry: Fast line (TEMA) crosses above slow line (LSMA)
Exit: Bearish crossunder OR take profit levels hit

Take Profits:
- TP1: 10% (exit 30% of position)
- TP2: 30% (exit 50% of position)
- Remaining 20% exits on crossunder

Parameters:
- LeadLine 1: TEMA(25) - fast, responsive
- LeadLine 2: LSMA(100) - slow, smooth
- Configurable MA types: TEMA, LSMA, EMA, SMA

Entry Filters:
- Weekly Candle Colour: Green (from PREVIOUS completed week - no lookahead)
- Weekly KER (10): > 0.4 (from PREVIOUS completed week - no lookahead)

CRITICAL: Uses PREVIOUS bar data only - no lookahead.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from core.strategy import Strategy
from utils.indicators import ATR, EMA, SMA


def TEMA(series: np.ndarray, length: int) -> np.ndarray:
    """Triple Exponential Moving Average: 3*EMA1 - 3*EMA2 + EMA3."""
    if length <= 0:
        return np.full_like(series, np.nan, dtype=float)
    ema1 = EMA(series, length)
    ema2 = EMA(ema1, length)
    ema3 = EMA(ema2, length)
    return 3 * ema1 - 3 * ema2 + ema3


def LSMA(series: np.ndarray, length: int) -> np.ndarray:
    """Least Squares Moving Average (Linear Regression)."""
    if length <= 0:
        return np.full_like(series, np.nan, dtype=float)
    result = np.full_like(series, np.nan, dtype=float)
    for i in range(length - 1, len(series)):
        x = np.arange(length)
        y = series[i - length + 1 : i + 1]
        x_mean, y_mean = np.mean(x), np.mean(y)
        m = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        b = y_mean - m * x_mean
        result[i] = m * (length - 1) + b
    return result


def kaufman_efficiency_ratio(close: np.ndarray, length: int) -> np.ndarray:
    """
    Kaufman Efficiency Ratio (KER) - measures trend strength vs noise.
    
    Formula:
        ER = |Close[t] - Close[t-n]| / Σ|Close[i] - Close[i-1]|  for i = t-n+1 to t
    
    Returns NaN for first `length` bars. Range: 0.0 to 1.0
    - Values < 0.3: High noise (mean-reverting)
    - Values > 0.7: Low noise (trending)
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    ker = np.full(n, np.nan, dtype=float)

    for i in range(length, n):
        # Direction: absolute change from length bars ago to current
        direction = abs(close[i] - close[i - length])

        # Volatility (noise): sum of ALL bar-to-bar absolute changes in window
        volatility = 0.0
        for j in range(i - length + 1, i + 1):
            volatility += abs(close[j] - close[j - 1])

        # Calculate ER
        if volatility > 0:
            ker[i] = direction / volatility
        else:
            ker[i] = 0.0

    return ker


MA_FUNCS = {"TEMA": TEMA, "LSMA": LSMA, "EMA": EMA, "SMA": SMA}


class TemaLsmaCrossover(Strategy):
    """
    TEMA-LSMA Crossover with multi-level take profits and weekly filters.

    Entry: Fast crosses above slow (requires weekly filters)
    Exit: Bearish crossunder or take profit levels
    TP1: 10% gain (30% exit), TP2: 30% gain (50% exit)
    
    Weekly Filters:
    - Weekly Candle Colour: Green (close > open)
    - Weekly KER (10): > 0.4 (trending market requirement)
    """

    # ===== MA PARAMETERS =====
    fast_type = "TEMA"
    fast_length = 25
    slow_type = "LSMA"
    slow_length = 100

    # ===== TAKE PROFITS =====
    tp1_pct = 0.05      # First take profit level (5%)
    tp1_qty_pct = 0.00  # Exit 0% at TP1
    tp2_pct = 0.10      # Second take profit level (10%)
    tp2_qty_pct = 0.00  # Exit 0% at TP2 (remaining 100% exits at signal)
    cap_tp_qtys = True  # Ensure TP1 + TP2 <= 100%

    # ===== ENTRY FILTERS =====
    use_atr_pct_filter = True   # ATR% > 3
    atr_pct_min = 3.0           # Minimum ATR% for entry
    atr_period = 14             # ATR period for filter

    # ===== WEEKLY FILTERS =====
    use_weekly_filters = True  # Enable weekly candle colour and KER filters
    weekly_ker_min = 0.4       # Minimum KER (10) for weekly trend
    require_weekly_green = True # Require weekly candle to be green

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and indicators."""
        self.data = df.copy()
        close = self.data.close.values
        high = self.data.high.values
        low = self.data.low.values

        # Calculate MAs based on type
        fast_func = MA_FUNCS.get(self.fast_type, TEMA)
        slow_func = MA_FUNCS.get(self.slow_type, LSMA)

        self.fast_line = self.I(
            fast_func, close, self.fast_length,
            name=f"{self.fast_type}({self.fast_length})",
            overlay=True, color="green"
        )
        self.slow_line = self.I(
            slow_func, close, self.slow_length,
            name=f"{self.slow_type}({self.slow_length})",
            overlay=True, color="red"
        )

        # ATR for volatility filter
        atr_vals = ATR(high, low, close, self.atr_period)
        self.atr = self.I(
            lambda: atr_vals,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

        # Load weekly data if filters enabled (will be called again after symbol is set)
        self.weekly_ker = np.full(len(close), np.nan)
        self.weekly_candle_colour = [''] * len(close)
        
        if self.use_weekly_filters:
            self._load_weekly_data()

        # Adjust TP qty if capped
        self._tp1_qty = self.tp1_qty_pct
        self._tp2_qty = self.tp2_qty_pct
        if self.cap_tp_qtys:
            self._tp2_qty = min(self.tp2_qty_pct, max(0, 1.0 - self.tp1_qty_pct))

        return super().prepare(df)

    def _set_symbol(self, symbol: str):
        """Set the symbol and load weekly data."""
        self.symbol = symbol
        if self.use_weekly_filters:
            self._load_weekly_data()

    def _load_weekly_data(self):
        """
        Load weekly data for the current symbol and calculate weekly KER and candle colour.
        Uses the same formula as consolidated trades file generation.
        """
        try:
            import glob
            
            # Check if symbol is available
            if not hasattr(self, 'symbol') or not self.symbol:
                return
            
            symbol = self.symbol
            
            # Load weekly data using glob pattern
            # Try multiple cache locations
            cache_dirs = [
                Path(__file__).parent.parent / 'cache',
                Path(__file__).parent.parent / 'data' / 'cache',
            ]
            
            weekly_df = None
            for cache_dir in cache_dirs:
                if not cache_dir.exists():
                    continue
                    
                # Look for weekly files matching the symbol
                pattern = str(cache_dir / f"**/*{symbol}*1w*.csv")
                files = glob.glob(pattern, recursive=True)
                
                if files:
                    # Load the first matching file
                    try:
                        weekly_df = pd.read_csv(files[0])
                        break
                    except:
                        continue
            
            if weekly_df is None or weekly_df.empty:
                return
            
            # Standardize column names
            weekly_df.columns = weekly_df.columns.str.lower()
            
            # Ensure we have required columns
            required_cols = ['time', 'open', 'close']
            if not all(col in weekly_df.columns for col in required_cols):
                return
            
            # Convert time to datetime
            weekly_df['time'] = pd.to_datetime(weekly_df['time'])
            weekly_df = weekly_df.sort_values('time').reset_index(drop=True)
            
            # Ensure daily data is sorted
            if hasattr(self, 'data') and self.data is not None:
                self.data = self.data.sort_index()
                
                # Convert daily index to datetime if needed
                if not isinstance(self.data.index, pd.DatetimeIndex):
                    return
                
                # Calculate weekly KER and candle colour
                # KER calculation uses historical data only (lookback window)
                # No lookahead bias in the KER formula itself
                weekly_close = weekly_df['close'].values
                weekly_open = weekly_df['open'].values
                
                # Calculate weekly KER (10) - measures trend strength of past 10 weeks
                weekly_ker = kaufman_efficiency_ratio(weekly_close, 10)
                
                # Calculate weekly candle colour (green if close > open)
                weekly_candle_colour = np.where(
                    weekly_close > weekly_open, 
                    'green', 
                    np.where(weekly_close < weekly_open, 'red', 'doji')
                )
                
                # Map weekly values to daily bars using ONLY COMPLETED WEEKS
                # Critical: Uses strict < comparison to avoid lookahead bias
                # Example: Mon Jan 1 maps to week ending Dec 31 (previous completed week)
                for i, daily_date in enumerate(self.data.index):
                    # Find the week this daily date belongs to
                    # Get the weekly candle BEFORE the current week (completed week)
                    daily_date_only = daily_date.date()
                    
                    # Use weekly candles from BEFORE current week
                    weekly_mask = weekly_df['time'].dt.date < daily_date_only
                    
                    if weekly_mask.any():
                        # Get the index of the last True value (most recent completed week)
                        matching_indices = np.where(weekly_mask)[0]
                        if len(matching_indices) > 0:
                            latest_week_idx = matching_indices[-1]
                            self.weekly_ker[i] = weekly_ker[latest_week_idx]
                            self.weekly_candle_colour[i] = weekly_candle_colour[latest_week_idx]
                
                # Forward fill any NaN values within the week
                weekly_ker_series = pd.Series(self.weekly_ker, index=self.data.index)
                self.weekly_ker = weekly_ker_series.ffill().values
            
        except Exception as e:
            # Silently fail - weekly data not available
            pass

    def _get_atr_pct(self, idx, close):
        """Calculate ATR as percentage of price at bar index."""
        if close <= 0:
            return 0.0
        try:
            atr_val = self.atr[idx] if hasattr(self.atr, '__getitem__') else self.atr.iloc[idx]
            if np.isnan(atr_val):
                return 0.0
            return (atr_val / close) * 100
        except (IndexError, KeyError):
            return 0.0

    def on_entry(self, entry_time, entry_price, state):
        """Calculate TP levels at entry. No stop loss by default."""
        # TP levels will be set after entry is confirmed in on_bar
        return {}

    def on_bar(self, ts, row, state):
        """Trading logic on each bar.
        
        TP Logic (matching TradingView):
        - At bar X, we check if bar X-1's HIGH >= TP price
        - If so, we fill at TP price (limit order simulation)
        - We only know bar X-1 completed when we're at bar X
        
        Entry Filters:
        - Weekly Candle Colour must be green
        - Weekly KER (10) must be > 0.4
        """
        try:
            idx_result = self.data.index.get_loc(ts)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        min_bars = max(self.fast_length, self.slow_length)
        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Get indicator values
        fast_now = self.fast_line[idx]
        fast_prev = self.fast_line[idx - 1]
        slow_now = self.slow_line[idx]
        slow_prev = self.slow_line[idx - 1]

        # NaN check
        if any(np.isnan(v) for v in [fast_now, fast_prev, slow_now, slow_prev]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Crossover detection
        bull_cross = (fast_prev <= slow_prev) and (fast_now > slow_now)
        bear_cross = (fast_prev >= slow_prev) and (fast_now < slow_now)

        in_position = state.get("qty", 0) > 0
        
        enter_long = False
        exit_long = False
        signal_reason = ""
        partial_exits = []  # List of {qty_pct, fill_price, reason, fill_time}

        # ATR% filter: Require minimum volatility for entry
        filters_pass = True
        if self.use_atr_pct_filter:
            atr_pct = self._get_atr_pct(idx, row.close)
            filters_pass = atr_pct >= self.atr_pct_min

        # Weekly filters
        if filters_pass and self.use_weekly_filters:
            # Check weekly candle colour
            if self.require_weekly_green:
                weekly_colour = self.weekly_candle_colour[idx] if idx < len(self.weekly_candle_colour) else ''
                if weekly_colour != 'green':
                    filters_pass = False
            
            # Check weekly KER (10)
            if filters_pass:
                weekly_ker = self.weekly_ker[idx] if idx < len(self.weekly_ker) else np.nan
                if np.isnan(weekly_ker) or weekly_ker < self.weekly_ker_min:
                    filters_pass = False

        # Entry on bullish crossover (only if filters pass)
        if not in_position and bull_cross and filters_pass:
            enter_long = True
            signal_reason = "Bull Cross + Weekly Filters"

        # Exit logic when in position
        if in_position:
            # Get previous bar data for TP checking
            prev_row = self.data.iloc[idx - 1]
            prev_high = float(prev_row["high"])
            prev_time = self.data.index[idx - 1]
            
            # Get TP prices from state (set by engine after entry)
            tp1_price = state.get("tp1_price")
            tp2_price = state.get("tp2_price")
            tp1_hit = state.get("tp1_hit", False)
            tp2_hit = state.get("tp2_hit", False)
            
            # Check TP1: if prev bar's high >= TP1 price, fill at TP1
            if tp1_price and not tp1_hit and prev_high >= tp1_price:
                partial_exits.append({
                    "qty_pct": self._tp1_qty,
                    "fill_price": tp1_price,
                    "reason": "TP1",
                    "fill_time": prev_time,
                })
                state["tp1_hit"] = True
            
            # Check TP2: if prev bar's high >= TP2 price, fill at TP2
            if tp2_price and not tp2_hit and prev_high >= tp2_price:
                partial_exits.append({
                    "qty_pct": self._tp2_qty,
                    "fill_price": tp2_price,
                    "reason": "TP2",
                    "fill_time": prev_time,
                })
                state["tp2_hit"] = True

            # Exit remaining on bearish crossunder
            if bear_cross:
                exit_long = True
                signal_reason = "XDN"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
            "partial_exits": partial_exits,
        }

    def next(self):
        """Legacy - not used by QuantLab engine."""
        pass
