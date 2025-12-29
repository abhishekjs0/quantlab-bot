#!/usr/bin/env python3
"""
Supertrend + DEMA Strategy

Replicates TradingView Pine Script v6 "Supertrend Strategy + DEMA":
- Entry when in trend AND filter condition met (any bar, not just flips)
- Exit ONLY on trend flip

INDICATORS:
1. Supertrend(factor=3.0, atrPeriod=12) - Main trend indicator
2. DEMA(200) - Double Exponential Moving Average filter

ENTRY CONDITIONS (checked every bar):
- Long:  isUp (direction < 0) AND (no filter OR ST > DEMA) AND not already long
- Short: isDown (direction > 0) AND (no filter OR ST < DEMA) AND not already short

EXIT CONDITIONS (ONLY on flips, independent of DEMA):
- Long exit:  downFlip (direction went from < 0 to > 0)
- Short exit: upFlip (direction went from > 0 to < 0)
"""

import numpy as np
import pandas as pd

from core.loaders import load_india_vix, load_nifty200
from core.strategy import Strategy
from utils import EMA, RSI
from utils.indicators import ATR, CHOP, DEMA, Supertrend


class SupertrendDEMAStrategy(Strategy):
    """
    Supertrend + DEMA Trend Following Strategy
    
    Uses Supertrend indicator for trend direction and DEMA as entry filter.
    Entries can happen on ANY bar where conditions are met.
    Exits happen ONLY on trend flips.
    """

    # ===== SUPERTREND PARAMETERS =====
    atr_period = 12  # ATR Length for Supertrend
    factor = 3.0     # Supertrend multiplier

    # ===== DEMA PARAMETERS =====
    dema_len = 200   # DEMA Length
    use_dema_filter = False  # Use DEMA filter for entries only

    # ===== TRADING CONTROLS =====
    allow_longs = True    # Allow long entries
    allow_shorts = False  # Allow short entries

    # ===== RISK MANAGEMENT - ATR-BASED STOP LOSS =====
    atr_multiplier = 5.0  # 5 ATR stop loss
    use_stop_loss = False   # DISABLED for comparison

    # ===== ENTRY FILTERS =====
    use_chop_filter = False   # Filter: DISABLED
    use_vix_filter = True     # Filter: VIX < 13 OR VIX > 19
    use_atr_pct_filter = True # Filter: ATR% > 3
    use_rsi_filter = False    # Filter: DISABLED
    use_nifty200_ema_filter = False  # Filter: DISABLED
    
    # Filter thresholds
    chop_threshold = 50.0  # CHOP >= 50 = Choppy/Very Choppy (OK to trade, CHOP < 50 = skip)
    vix_min = 13.0         # VIX lower bound to AVOID (trade when VIX < 13)
    vix_max = 19.0         # VIX upper bound to AVOID (trade when VIX > 19)
    atr_pct_min = 3.0      # Minimum ATR% for entry
    rsi_threshold = 50.0   # RSI must be > 50 for entry
    rsi_period = 14        # RSI period

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides."""
        super().__init__()

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.name = "Supertrend + DEMA"
        self.description = (
            f"Supertrend({self.factor}, {self.atr_period}) + DEMA({self.dema_len}). "
            f"DEMA Filter: {'ON' if self.use_dema_filter else 'OFF'}. "
            f"Longs: {'ON' if self.allow_longs else 'OFF'}, "
            f"Shorts: {'ON' if self.allow_shorts else 'OFF'}"
        )

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""
        # ATR for stop loss calculation
        atr_vals = ATR(
            self.data.high.values,
            self.data.low.values,
            self.data.close.values,
            self.atr_period,
        )
        self.atr = self.I(
            lambda: atr_vals,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )
        
        # Supertrend indicator from utils
        st_result = Supertrend(
            self.data.high.values,
            self.data.low.values,
            self.data.close.values,
            self.atr_period,
            self.factor,
        )
        
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

        # CHOP (Choppiness Index) from utils - for choppy market filter
        chop_vals = CHOP(
            self.data.high.values,
            self.data.low.values,
            self.data.close.values,
            period=50
        )
        self.chop = self.I(
            lambda: chop_vals,
            name="CHOP(50)",
            overlay=False,
            plot=True,
        )

        # DEMA indicator from utils
        dema_vals = DEMA(self.data.close.values, self.dema_len)
        self.dema = self.I(
            lambda: dema_vals,
            name=f"DEMA({self.dema_len})",
            overlay=True,
            color="#43A047",
        )

        # RSI(14) indicator for momentum filter
        rsi_vals = RSI(self.data.close.values, self.rsi_period)
        self.rsi = self.I(
            lambda: rsi_vals,
            name=f"RSI({self.rsi_period})",
            overlay=False,
        )

        # Load India VIX for sentiment filter
        try:
            vix_df = load_india_vix()
            # Get VIX close values
            vix_close = vix_df['close'] if 'close' in vix_df.columns else vix_df['Close']
            vix_series = pd.Series(vix_close.values, index=pd.to_datetime(vix_df.index).normalize())
            # Align VIX with stock data by date using forward-fill
            stock_dates = pd.to_datetime(self.data.index).normalize()
            self.vix_aligned = vix_series.reindex(stock_dates, method='ffill')
        except Exception:
            # If VIX data not available, VIX filter will return None and be skipped
            self.vix_aligned = None

        # Load NIFTY200 > EMA50 for market regime filter
        try:
            nifty200_df = load_nifty200()
            nifty200_close = nifty200_df['close'].values
            nifty200_ema50 = EMA(nifty200_close, 50)
            nifty200_above_ema50 = pd.Series(
                nifty200_close > nifty200_ema50,
                index=pd.to_datetime(nifty200_df.index).normalize()
            )
            stock_dates = pd.to_datetime(self.data.index).normalize()
            self.nifty200_above_ema50 = nifty200_above_ema50.reindex(stock_dates, method='ffill')
        except Exception:
            # If NIFTY200 data not available, filter will be skipped
            self.nifty200_above_ema50 = None

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate ATR-based stop loss when entering a trade.

        Stop loss is FIXED at entry time (not trailing). Calculated as:
        stop_loss = entry_price - (ATR_at_entry × atr_multiplier)
        
        The stop is checked against bar LOW - if low < stop, exit at stop price.
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result

            # Use previous bar's ATR for decision (avoid look-ahead)
            decision_idx = idx - 1 if idx > 0 else idx
            if decision_idx >= 0 and decision_idx < len(self.atr):
                atr_value = self.atr[decision_idx]
                if atr_value is not None and not np.isnan(atr_value) and atr_value > 0:
                    stop_loss = entry_price - (atr_value * self.atr_multiplier)
                    return {"stop": stop_loss}
        except Exception:
            pass

        return {}

    def _get_india_vix(self, idx):
        """
        Get India VIX value at specific bar index.
        
        India VIX (NIFTY VIX) is the volatility index for Indian markets.
        - VIX 13-19: Neutral sentiment (skip entries)
        - VIX < 13: Very low fear (complacent market)
        - VIX > 19: Fear/high volatility (good opportunity)
        
        Returns:
            Float value of India VIX, or None if data unavailable
        """
        if self.vix_aligned is None:
            return None
        
        try:
            val = self.vix_aligned.iloc[idx]
            return val if not np.isnan(val) else None
        except (IndexError, KeyError):
            return None

    def _calculate_atr_pct(self, atr_value, close_value):
        """Calculate ATR as percentage of price."""
        if np.isnan(close_value) or close_value <= 0 or np.isnan(atr_value):
            return 0
        return (atr_value / close_value) * 100

    def _at(self, x, i):
        """Accessor: safely get element at index i from Series or array."""
        return x.iloc[i] if hasattr(x, "iloc") else x[i]

    def on_bar(self, ts, row, state):
        """
        Generate signals on each bar.
        
        Entry: ANY bar where trend + filter conditions are met.
        Exit: ONLY on trend flips (independent of DEMA).
        """
        # Get index of current bar
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, 
                    "enter_short": False, "exit_short": False, "signal_reason": ""}

        # Need at least 2 bars for flip detection
        if idx is None or idx < 1:
            return {"enter_long": False, "exit_long": False,
                    "enter_short": False, "exit_short": False, "signal_reason": ""}

        # ========== GET INDICATOR VALUES ==========
        st_now = self._at(self.supertrend, idx)
        dir_now = self._at(self.direction, idx)
        dir_prev = self._at(self.direction, idx - 1)
        dema_now = self._at(self.dema, idx)

        # Check for valid values
        if any(np.isnan(x) for x in [st_now, dir_now, dir_prev, dema_now]):
            return {"enter_long": False, "exit_long": False,
                    "enter_short": False, "exit_short": False, "signal_reason": ""}

        # ========== TREND STATE ==========
        # Direction convention: < 0 = uptrend (green), > 0 = downtrend (red)
        is_up = dir_now < 0
        is_down = dir_now > 0

        # Trend flips (for exits only)
        up_flip = dir_prev > 0 and dir_now < 0    # downtrend -> uptrend
        down_flip = dir_prev < 0 and dir_now > 0  # uptrend -> downtrend

        # ========== ENTRY FILTERS ==========
        # Long filter: supertrend line above DEMA (or filter disabled)
        long_entry_filter_ok = (not self.use_dema_filter) or (st_now > dema_now)
        # Short filter: supertrend line below DEMA (or filter disabled)
        short_entry_filter_ok = (not self.use_dema_filter) or (st_now < dema_now)

        # ========== MARKET CONDITION FILTERS ==========
        # All filters use SIGNAL BAR (idx) - the bar where decision is made
        # Entry happens on NEXT bar at open
        
        # CHOP filter: Only trade in choppy markets (CHOP >= 50: Choppy or Very Choppy)
        # Skip in trending markets (CHOP < 50: Trending or Strong Trend)
        chop_now = self._at(self.chop, idx)
        chop_filter_ok = True
        if self.use_chop_filter:
            chop_filter_ok = not np.isnan(chop_now) and chop_now >= self.chop_threshold

        # VIX filter: VIX < 13 OR VIX > 19 (avoid neutral zone 13-19)
        # Use signal bar (idx) - matches what's reported in consolidated trades
        vix_filter_ok = True
        if self.use_vix_filter:
            vix = self._get_india_vix(idx)
            if vix is not None:
                # Pass if VIX < 13 OR VIX > 19 (outside neutral zone)
                vix_filter_ok = (vix < self.vix_min) or (vix > self.vix_max)
            else:
                # Fail filter if VIX data is missing (don't trade blind)
                vix_filter_ok = False

        # ATR% filter: Require minimum volatility (ATR% > 3)
        # Use signal bar (idx) - matches what's reported in consolidated trades
        atr_now = self._at(self.atr, idx)
        atr_pct = self._calculate_atr_pct(atr_now, row.close)
        atr_pct_filter_ok = True
        if self.use_atr_pct_filter:
            atr_pct_filter_ok = atr_pct >= self.atr_pct_min

        # RSI filter: RSI(14) > 50 (bullish momentum)
        # Use signal bar (idx) - matches what's reported in consolidated trades
        rsi_filter_ok = True
        if self.use_rsi_filter:
            rsi_now = self._at(self.rsi, idx)
            if not np.isnan(rsi_now):
                rsi_filter_ok = rsi_now > self.rsi_threshold
            else:
                # Fail filter if RSI data is missing
                rsi_filter_ok = False

        # NIFTY200 > EMA50 filter (market regime)
        # Use signal bar (idx) - matches what's reported in consolidated trades
        nifty200_filter_ok = True
        if self.use_nifty200_ema_filter:
            if self.nifty200_above_ema50 is not None:
                try:
                    nifty200_above = self.nifty200_above_ema50.iloc[idx]
                    nifty200_filter_ok = bool(nifty200_above) if not pd.isna(nifty200_above) else False
                except (IndexError, KeyError):
                    nifty200_filter_ok = False
            else:
                # Fail filter if NIFTY200 data is missing
                nifty200_filter_ok = False

        # ========== POSITION STATE ==========
        qty = state.get("qty", 0)
        position_side = state.get("position_side", None)
        in_long = position_side == "long" or qty > 0
        in_short = position_side == "short" or qty < 0

        # ========== EXITS (ONLY on flips, independent of DEMA) ==========
        exit_long = in_long and down_flip
        exit_short = in_short and up_flip

        # ========== ENTRIES (any bar where conditions met) ==========
        # Long: in uptrend + DEMA filter ok + market filters ok + longs allowed + not already long
        enter_long = (
            self.allow_longs
            and is_up
            and long_entry_filter_ok
            and chop_filter_ok
            and vix_filter_ok
            and atr_pct_filter_ok
            and rsi_filter_ok
            and nifty200_filter_ok
            and not in_long
        )

        # Short: in downtrend + DEMA filter ok + market filters ok + shorts allowed + not already short
        enter_short = (
            self.allow_shorts
            and is_down
            and short_entry_filter_ok
            and chop_filter_ok
            and vix_filter_ok
            and atr_pct_filter_ok
            and rsi_filter_ok
            and nifty200_filter_ok
            and not in_short
        )

        # ========== SIGNAL REASONS ==========
        signal_reason = ""
        if enter_long:
            signal_reason = f"LONG: uptrend, ST={st_now:.2f}"
            if self.use_dema_filter:
                signal_reason += f" > DEMA={dema_now:.2f}"
            if self.use_chop_filter:
                signal_reason += f", CHOP={chop_now:.1f}"
            if self.use_atr_pct_filter:
                signal_reason += f", ATR%={atr_pct:.1f}"
        elif enter_short:
            signal_reason = f"SHORT: downtrend, ST={st_now:.2f}"
            if self.use_dema_filter:
                signal_reason += f" < DEMA={dema_now:.2f}"
        elif exit_long:
            signal_reason = "EXIT LONG: flip to red"
        elif exit_short:
            signal_reason = "EXIT SHORT: flip to green"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "enter_short": enter_short,
            "exit_short": exit_short,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
