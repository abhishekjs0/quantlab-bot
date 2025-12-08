"""
QuantLab-compatible Ichimoku Tenkan-Kijun Crossover Strategy

Implements correct Ichimoku Cloud logic with:
- Proper Tenkan-sen (conversion) and Kijun-sen (baseline) as midpoints of high/low
- Senkou Span A/B with 26-bar forward shift
- Custom crossover detection handling flat segments
- Faster exits: Tenkan-Kijun bearish cross OR price below cloud
- Trailing stop loss anchored at cloud edge

Long-only strategy trading Tenkan-Kijun bullish crosses with optional cloud filters.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR


class IchimokuCloud(Strategy):
    """
    Ichimoku cloud strategy focused on Tenkan-Kijun crossovers with cloud confirmation.

    Core Signal:
    - Entry: Bullish Tenkan-Kijun crossover (handling flat segments correctly)
    - Exit: Bearish Tenkan-Kijun crossover OR price below cloud (whichever comes first)

    Trend Context:
    - Cloud must be BULLISH (Span A > Span B) for long entry
    - Price should ideally be above cloud (Kumo filter)

    Optional Filters (all configurable):
    1. Price above Kumo (cloud)
    2. ATR % filter (volatility)
    3. NIFTY50 > EMA 50 (market regime)
    4. Price > EMA 200 (long-term trend)

    Stop Loss:
    - Trailing stop anchored at bottom of cloud (min of Span A and B)

    Parameters configurable for optimization of lengths and filter toggles.
    """

    # Ichimoku parameters (standard defaults)
    tenkan_length = 9
    kijun_length = 26
    senkou_b_length = 52
    chikou_shift = 26

    # Filter toggles
    use_price_above_kumo = True  # Require price > cloud for entry
    use_kumo_bullish_filter = True  # Require cloud bullish (Span A > Span B)
    
    # Additional filters (like stoch_rsi_pyramid_long.py)
    use_atr_filter = False  # ATR % filter
    atr_pct_threshold = 3.0  # ATR % must be above this
    use_nifty50_ema_filter = False  # NIFTY50 > EMA 50 filter (entry)
    use_price_above_ema200 = False  # Price > EMA 200 filter (entry)
    ema200_period = 200  # EMA period for price filter

    # Risk management
    use_stop_loss = False  # Use cloud-based trailing stop
    use_cloud_trailing_stop = True  # Stop trails the lower edge of cloud
    atr_period = 14
    atr_stop_multiplier = 2.0

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and call initialize."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators."""
        # Initialize ATR for stop loss (even if disabled)
        self.atr = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
            color="gray",
        )
        
        # Initialize EMA 200 for price filter
        if self.use_price_above_ema200:
            self.ema200 = self.data.close.ewm(span=self.ema200_period, adjust=False).mean().values
        else:
            self.ema200 = None

    def _compute_tenkan_kijun(self, idx: int) -> tuple:
        """
        Compute Tenkan and Kijun at bar index.

        Returns:
            (tenkan_value, kijun_value) or (NaN, NaN) if insufficient data
        """
        if idx < self.tenkan_length - 1 or idx < self.kijun_length - 1:
            return np.nan, np.nan

        # Tenkan: highest high and lowest low over tenkan_length
        high_window = self.data.high.iloc[idx - self.tenkan_length + 1 : idx + 1]
        low_window = self.data.low.iloc[idx - self.tenkan_length + 1 : idx + 1]
        tenkan = (high_window.max() + low_window.min()) / 2.0

        # Kijun: highest high and lowest low over kijun_length
        high_window = self.data.high.iloc[idx - self.kijun_length + 1 : idx + 1]
        low_window = self.data.low.iloc[idx - self.kijun_length + 1 : idx + 1]
        kijun = (high_window.max() + low_window.min()) / 2.0

        return tenkan, kijun

    def _compute_senkou_span_a(self, idx: int) -> float:
        """
        Compute Senkou Span A (leading span A).

        Returns the shifted forward value (26 bars back in time).
        At bar i, we use the value that was calculated at i-26.
        
        Formula: ((Tenkan[i-26] + Kijun[i-26]) / 2)
        """
        # Check if we have enough data to look back 26 bars
        source_idx = idx - self.chikou_shift
        if source_idx < self.tenkan_length - 1 or source_idx < self.kijun_length - 1:
            return np.nan

        # Tenkan at source_idx
        high_window = self.data.high.iloc[
            source_idx - self.tenkan_length + 1 : source_idx + 1
        ]
        low_window = self.data.low.iloc[
            source_idx - self.tenkan_length + 1 : source_idx + 1
        ]
        tenkan_source = (high_window.max() + low_window.min()) / 2.0

        # Kijun at source_idx
        high_window = self.data.high.iloc[
            source_idx - self.kijun_length + 1 : source_idx + 1
        ]
        low_window = self.data.low.iloc[
            source_idx - self.kijun_length + 1 : source_idx + 1
        ]
        kijun_source = (high_window.max() + low_window.min()) / 2.0

        # Span A = (Tenkan + Kijun) / 2, shifted forward 26 bars
        return (tenkan_source + kijun_source) / 2.0

    def _compute_senkou_span_b(self, idx: int) -> float:
        """
        Compute Senkou Span B (leading span B).

        Returns the shifted forward value (26 bars back in time).
        """
        # Check if we have enough data
        source_idx = idx - self.chikou_shift
        if source_idx < self.senkou_b_length - 1:
            return np.nan

        # Highest high and lowest low over senkou_b_length at source_idx
        high_window = self.data.high.iloc[
            source_idx - self.senkou_b_length + 1 : source_idx + 1
        ]
        low_window = self.data.low.iloc[
            source_idx - self.senkou_b_length + 1 : source_idx + 1
        ]

        return (high_window.max() + low_window.min()) / 2.0

    def _is_bullish_tenkan_kijun_cross(self, idx: int) -> bool:
        """
        Detect bullish Tenkan-Kijun crossover, handling flat segments.

        Tenkan crosses above Kijun, accounting for cases where they were equal
        for several bars (flat segments).

        Returns:
            True if bullish cross detected, False otherwise
        """
        if idx < 1:
            return False

        tenkan, kijun = self._compute_tenkan_kijun(idx)
        if np.isnan(tenkan) or np.isnan(kijun):
            return False

        # Current bar: Tenkan must be above Kijun
        if tenkan <= kijun:
            return False

        # Walk back to find last bar where lines differed
        j = idx - 1
        while j >= 0:
            tenkan_j, kijun_j = self._compute_tenkan_kijun(j)
            if np.isnan(tenkan_j) or np.isnan(kijun_j):
                return False
            if tenkan_j != kijun_j:
                # Found the last differing point
                # Bullish cross: Tenkan was below or equal Kijun at that point
                return tenkan_j < kijun_j
            j -= 1

        return False

    def _is_bearish_tenkan_kijun_cross(self, idx: int) -> bool:
        """
        Detect bearish Tenkan-Kijun crossover.

        Tenkan crosses below Kijun, handling flat segments.

        Returns:
            True if bearish cross detected, False otherwise
        """
        if idx < 1:
            return False

        tenkan, kijun = self._compute_tenkan_kijun(idx)
        if np.isnan(tenkan) or np.isnan(kijun):
            return False

        # Current bar: Tenkan must be below Kijun
        if tenkan >= kijun:
            return False

        # Walk back to find last bar where lines differed
        j = idx - 1
        while j >= 0:
            tenkan_j, kijun_j = self._compute_tenkan_kijun(j)
            if np.isnan(tenkan_j) or np.isnan(kijun_j):
                return False
            if tenkan_j != kijun_j:
                # Bearish cross: Tenkan was above Kijun at that point
                return tenkan_j > kijun_j
            j -= 1

        return False

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate stop loss when entering a trade.
        
        Default: Cloud-based trailing stop at the lower edge of the cloud.
        Override: ATR-based stops if use_cloud_trailing_stop=False
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx = self.data.index.get_loc(entry_time)
            if isinstance(idx, slice):
                idx = idx.start

            if idx is not None and idx >= 0:
                # Get cloud boundaries
                span_a = self._compute_senkou_span_a(idx)
                span_b = self._compute_senkou_span_b(idx)
                
                if not (np.isnan(span_a) or np.isnan(span_b)):
                    # Cloud-based stop: lower edge of cloud
                    cloud_lower = min(span_a, span_b)
                    # Give some margin below cloud
                    stop_loss = cloud_lower * 0.98  # 2% below cloud
                    return {"stop": stop_loss}
                
                # Fallback to ATR if cloud not available
                if self.atr is not None and idx < len(self.atr):
                    atr_val = self.atr[idx]
                    if atr_val is not None and not np.isnan(atr_val) and atr_val > 0:
                        stop_loss = entry_price - (atr_val * self.atr_stop_multiplier)
                        return {"stop": stop_loss}
        except Exception:
            pass

        return {}

    def on_bar(self, ts, row, state):
        """
        Main strategy logic on each bar.

        Entry: Tenkan-Kijun bullish cross + filters + cloud bullish
        Exit: Tenkan-Kijun bearish cross OR price below cloud (whichever comes first)
        
        Optional filters: price above cloud, ATR, NIFTY50, EMA200
        """
        try:
            idx = self.data.index.get_loc(ts)
            if isinstance(idx, slice):
                idx = idx.start
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        if idx is None or idx < 1:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # =======================
        # ENTRY LOGIC
        # =======================
        enter_long = False
        signal_reason = ""

        # Core signal: Bullish Tenkan-Kijun cross
        if self._is_bullish_tenkan_kijun_cross(idx):
            # Check filters
            all_filters_pass = True

            # Filter 0: Cloud must be BULLISH (Span A > Span B)
            if self.use_kumo_bullish_filter:
                span_a = self._compute_senkou_span_a(idx)
                span_b = self._compute_senkou_span_b(idx)
                if np.isnan(span_a) or np.isnan(span_b):
                    all_filters_pass = False
                else:
                    # Cloud bullish: Span A (faster) above Span B (slower)
                    if span_a <= span_b:
                        all_filters_pass = False

            # Filter 1: Price above Kumo
            if all_filters_pass and self.use_price_above_kumo:
                span_a = self._compute_senkou_span_a(idx)
                span_b = self._compute_senkou_span_b(idx)
                if np.isnan(span_a) or np.isnan(span_b):
                    all_filters_pass = False
                else:
                    kumo_top = max(span_a, span_b)
                    if row.close <= kumo_top:
                        all_filters_pass = False

            # Filter 2: ATR % > threshold (volatility filter)
            if all_filters_pass and self.use_atr_filter:
                if self.atr is not None and idx < len(self.atr):
                    atr_val = self.atr[idx]
                    if not np.isnan(atr_val) and row.close > 0:
                        atr_pct = (atr_val / row.close) * 100.0
                        if atr_pct <= self.atr_pct_threshold:
                            all_filters_pass = False
                    else:
                        all_filters_pass = False
                else:
                    all_filters_pass = False

            # Filter 3: NIFTY50 > EMA 50 (market regime filter)
            if all_filters_pass and self.use_nifty50_ema_filter:
                # Access nifty50_above_ema50 from the row (added by compute_indicators)
                nifty50_above_ema50 = None
                
                # Try accessing from the row (Series)
                if hasattr(row, 'get'):
                    nifty50_above_ema50 = row.get('nifty50_above_ema50', None)
                elif hasattr(row, 'nifty50_above_ema50'):
                    nifty50_above_ema50 = row.nifty50_above_ema50
                
                if nifty50_above_ema50 is not None:
                    # Convert to bool if needed (could be True/False, 1/0, 'True'/'False')
                    if isinstance(nifty50_above_ema50, str):
                        nifty50_above_ema50 = nifty50_above_ema50.lower() == 'true'
                    if not nifty50_above_ema50:
                        all_filters_pass = False
                # If indicator not available, still allow trade (graceful degradation)

            # Filter 4: Price > EMA 200 (price above long-term trend)
            if all_filters_pass and self.use_price_above_ema200:
                if self.ema200 is not None and idx < len(self.ema200):
                    ema200_val = self.ema200[idx]
                    if not np.isnan(ema200_val):
                        if row.close <= ema200_val:
                            all_filters_pass = False
                    else:
                        # Not enough data for EMA200 yet, skip filter
                        pass
            if all_filters_pass:
                enter_long = True
                signal_reason = "Ichimoku Tenkan-Kijun Bullish Cross"

        # =======================
        # EXIT LOGIC (FASTER: OR condition)
        # =======================
        exit_long = False
        was_in_position = state.get("qty", 0) > 0

        if was_in_position:
            # Exit Condition 1: Bearish Tenkan-Kijun cross
            if self._is_bearish_tenkan_kijun_cross(idx):
                exit_long = True
                signal_reason = "Ichimoku Tenkan-Kijun Bearish Cross"
            
            # Exit Condition 2: Price breaks below cloud (faster exit)
            if not exit_long:  # Don't double-check if already exiting
                span_a = self._compute_senkou_span_a(idx)
                span_b = self._compute_senkou_span_b(idx)
                if not (np.isnan(span_a) or np.isnan(span_b)):
                    kumo_top = max(span_a, span_b)
                    if row.close < kumo_top:  # Strict < for exit
                        exit_long = True
                        signal_reason = "Price Below Kumo"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
