#!/usr/bin/env python3
"""
Supertrend VIX+ATR% Strategy

A streamlined trend-following strategy using Supertrend indicator with
VIX regime and ATR% volatility filters.

CORE LOGIC:
- Entry: When in uptrend (Supertrend green) AND filters pass
- Exit: ONLY on trend flip (Supertrend turns red)

FILTERS (applied at signal bar):
1. VIX Filter: Trade when VIX < 13 OR VIX > 19 (avoid neutral 13-19 zone)
2. ATR% Filter: Trade when ATR% > 3 (require minimum volatility)

KEY DESIGN DECISIONS:
- Filters only affect ENTRY, never exit
- Exit purely on trend reversal (Supertrend flip)
- No stop loss (filters already ensure quality entries)
- Long-only (shorts disabled)
"""

import numpy as np
import pandas as pd

from core.loaders import load_india_vix
from core.strategy import Strategy
from utils.indicators import ATR, Supertrend


class SupertrendVixAtrStrategy(Strategy):
    """
    Supertrend with VIX + ATR% Entry Filters
    
    Uses Supertrend for trend direction with VIX regime and ATR% 
    volatility filters to improve entry quality.
    """

    # ===== SUPERTREND PARAMETERS =====
    atr_period = 12  # ATR period for Supertrend calculation
    factor = 3.0     # Supertrend multiplier

    # ===== TRADING CONTROLS =====
    allow_longs = True    # Allow long entries
    allow_shorts = False  # Allow short entries (disabled)

    # ===== ENTRY FILTERS =====
    use_vix_filter = True      # VIX < 13 OR VIX > 19
    use_atr_pct_filter = True  # ATR% > 3
    
    # Filter thresholds
    vix_low = 13.0      # Trade when VIX below this (low fear)
    vix_high = 19.0     # Trade when VIX above this (high fear)
    atr_pct_min = 3.0   # Minimum ATR% for entry

    # ===== RISK MANAGEMENT =====
    use_stop_loss = False  # Disabled (exit on trend flip only)
    atr_stop_multiplier = 5.0  # ATR multiplier if stop loss enabled

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides."""
        super().__init__()

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.name = "Supertrend VIX+ATR%"
        self.description = (
            f"Supertrend({self.factor}, {self.atr_period}) with "
            f"VIX filter (<{self.vix_low} or >{self.vix_high}) and "
            f"ATR% filter (>{self.atr_pct_min}%)"
        )

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self._initialize_indicators()
        return super().prepare(df)

    def _initialize_indicators(self):
        """Initialize all required indicators."""
        high = self.data.high.values
        low = self.data.low.values
        close = self.data.close.values

        # ATR for volatility filter
        atr_vals = ATR(high, low, close, self.atr_period)
        self.atr = self.I(
            lambda: atr_vals,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )
        
        # Supertrend indicator
        st_result = Supertrend(high, low, close, self.atr_period, self.factor)
        
        self.supertrend = self.I(
            lambda: st_result["supertrend"],
            name=f"Supertrend({self.factor}, {self.atr_period})",
            overlay=True,
        )
        
        self.direction = self.I(
            lambda: st_result["direction"],
            name="ST_Direction",
            overlay=False,
            plot=False,
        )

        # Load and align India VIX data
        self.vix_aligned = self._load_vix_data()

    def _load_vix_data(self):
        """Load India VIX and align with stock data dates."""
        try:
            vix_df = load_india_vix()
            vix_close = vix_df['close'] if 'close' in vix_df.columns else vix_df['Close']
            vix_series = pd.Series(
                vix_close.values, 
                index=pd.to_datetime(vix_df.index).normalize()
            )
            stock_dates = pd.to_datetime(self.data.index).normalize()
            return vix_series.reindex(stock_dates, method='ffill')
        except Exception:
            return None

    def _get_vix(self, idx):
        """Get VIX value at bar index. Returns None if unavailable."""
        if self.vix_aligned is None:
            return None
        try:
            val = self.vix_aligned.iloc[idx]
            return float(val) if not np.isnan(val) else None
        except (IndexError, KeyError):
            return None

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
        """
        Calculate ATR-based stop loss when entering a trade.
        Uses signal bar ATR (bar before entry bar).
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx = self.data.index.get_loc(entry_time)
            if isinstance(idx, slice):
                idx = idx.start
            
            # Signal bar = entry bar - 1
            signal_idx = max(0, idx - 1)
            atr_val = self.atr[signal_idx]
            
            if atr_val is not None and not np.isnan(atr_val) and atr_val > 0:
                stop_price = entry_price - (atr_val * self.atr_stop_multiplier)
                return {"stop": stop_price}
        except Exception:
            pass

        return {}

    def on_bar(self, ts, row, state):
        """
        Generate trading signals on each bar.
        
        Signal bar (idx): Where decision is made at bar close
        Entry bar (idx+1): Where entry happens at open
        """
        # Get bar index
        try:
            idx = self.data.index.get_loc(ts)
            if isinstance(idx, slice):
                idx = idx.start
        except (KeyError, AttributeError):
            return self._no_signal()

        # Need at least 2 bars for trend flip detection
        if idx < 1:
            return self._no_signal()

        # ========== TREND STATE ==========
        dir_now = self.direction[idx]
        dir_prev = self.direction[idx - 1]
        
        if np.isnan(dir_now) or np.isnan(dir_prev):
            return self._no_signal()

        # Direction: < 0 = uptrend (green), > 0 = downtrend (red)
        is_uptrend = dir_now < 0
        is_downtrend = dir_now > 0
        
        # Trend flips (for exits)
        flip_to_downtrend = dir_prev < 0 and dir_now > 0
        flip_to_uptrend = dir_prev > 0 and dir_now < 0

        # ========== ENTRY FILTERS (signal bar) ==========
        filters_pass = True
        
        # VIX filter: Trade outside neutral zone (< 13 OR > 19)
        if filters_pass and self.use_vix_filter:
            vix = self._get_vix(idx)
            if vix is not None:
                filters_pass = (vix < self.vix_low) or (vix > self.vix_high)
            else:
                filters_pass = False  # No VIX data = no trade

        # ATR% filter: Require minimum volatility
        if filters_pass and self.use_atr_pct_filter:
            atr_pct = self._get_atr_pct(idx, row.close)
            filters_pass = atr_pct >= self.atr_pct_min

        # ========== POSITION STATE ==========
        in_long = state.get("qty", 0) > 0
        in_short = state.get("qty", 0) < 0

        # ========== EXITS (trend flip only, filters don't affect) ==========
        exit_long = in_long and flip_to_downtrend
        exit_short = in_short and flip_to_uptrend

        # ========== ENTRIES ==========
        enter_long = (
            self.allow_longs
            and is_uptrend
            and filters_pass
            and not in_long
        )
        
        enter_short = (
            self.allow_shorts
            and is_downtrend
            and filters_pass
            and not in_short
        )

        # ========== SIGNAL REASON ==========
        signal_reason = ""
        if enter_long:
            st_val = self.supertrend[idx]
            signal_reason = f"LONG: uptrend ST={st_val:.2f}"
        elif enter_short:
            st_val = self.supertrend[idx]
            signal_reason = f"SHORT: downtrend ST={st_val:.2f}"
        elif exit_long:
            signal_reason = "EXIT: trend flip to red"
        elif exit_short:
            signal_reason = "EXIT: trend flip to green"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "enter_short": enter_short,
            "exit_short": exit_short,
            "signal_reason": signal_reason,
        }

    def _no_signal(self):
        """Return no-signal response."""
        return {
            "enter_long": False,
            "exit_long": False,
            "enter_short": False,
            "exit_short": False,
            "signal_reason": "",
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
