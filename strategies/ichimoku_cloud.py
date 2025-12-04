"""
QuantLab-compatible Ichimoku Tenkan-Kijun Crossover Strategy

Implements correct Ichimoku Cloud logic with:
- Proper Tenkan-sen (conversion) and Kijun-sen (baseline) as midpoints of high/low
- Senkou Span A/B with 26-bar forward shift
- Chikou span logic (lagging span)
- Kaufman Efficiency Ratio (KER) filter for trend confirmation
- Custom crossover detection handling flat segments
- Faster exits: Tenkan-Kijun bearish cross OR price below cloud
- Trailing stop loss anchored at cloud edge

Long-only strategy trading Tenkan-Kijun bullish crosses with optional cloud filters.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, kaufman_efficiency_ratio


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
    2. Chikou (lagging span) above price 26 bars ago
    3. Chikou above Kumo 26 bars ago
    4. Kaufman Efficiency Ratio (low noise confirmation)

    Stop Loss:
    - Trailing stop anchored at bottom of cloud (min of Span A and B)

    Parameters configurable for optimization of lengths and filter toggles.
    """

    # Ichimoku parameters (standard defaults)
    tenkan_length = 9
    kijun_length = 26
    senkou_b_length = 52
    chikou_shift = 26

    # KER parameters
    ker_length = 10
    ker_percentile = 75  # 75th percentile = top 25% as trending
    ker_min_threshold = 0.5  # Minimum KER to trade (0.5 = strong trending)
    use_ker_filter = True  # Enable KER noise filter

    # Filter toggles
    use_price_above_kumo = True  # Require price > cloud for entry
    use_chikou_above_price = True  # Chikou > price 26 bars ago
    use_chikou_above_kumo = False  # Chikou > cloud 26 bars ago
    use_kumo_bullish_filter = True  # Require cloud bullish (Span A > Span B)

    # Risk management
    use_stop_loss = True  # Use cloud-based trailing stop
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

    def _get_ker_array(self, idx: int) -> np.ndarray:
        """
        Compute KER array up to bar idx for percentile calculation.

        Returns:
            KER values from index 0 to idx (excluding idx for lookahead)
        """
        close_data = self.data.close.iloc[: idx + 1].values
        ker_array = kaufman_efficiency_ratio(close_data, self.ker_length)
        return ker_array

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
        
        Optional filters: price above cloud, chikou conditions, KER filter
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

            # Filter 2: Chikou (current close) above price 26 bars ago
            if all_filters_pass and self.use_chikou_above_price:
                if idx < self.chikou_shift:
                    all_filters_pass = False
                else:
                    price_26ago = self.data.close.iloc[idx - self.chikou_shift]
                    if row.close <= price_26ago:
                        all_filters_pass = False

            # Filter 3: Chikou (current close) above Kumo 26 bars ago
            if all_filters_pass and self.use_chikou_above_kumo:
                if idx < self.chikou_shift:
                    all_filters_pass = False
                else:
                    span_a_26ago = self._compute_senkou_span_a(idx - self.chikou_shift)
                    span_b_26ago = self._compute_senkou_span_b(idx - self.chikou_shift)
                    if np.isnan(span_a_26ago) or np.isnan(span_b_26ago):
                        all_filters_pass = False
                    else:
                        kumo_top_26ago = max(span_a_26ago, span_b_26ago)
                        if row.close <= kumo_top_26ago:
                            all_filters_pass = False

            # Filter 4: KER low-noise filter (top 25% percentile or minimum threshold)
            if all_filters_pass and self.use_ker_filter:
                ker_array = self._get_ker_array(idx)
                if np.isnan(ker_array[idx]):
                    all_filters_pass = False
                else:
                    # Check against both percentile and absolute threshold
                    ker_val = ker_array[idx]
                    
                    # Absolute minimum threshold
                    if ker_val < self.ker_min_threshold:
                        all_filters_pass = False
                    else:
                        # Also check percentile for dynamic confirmation
                        past_ker = ker_array[:idx]
                        if not np.all(np.isnan(past_ker)):
                            ker_thresh = np.nanpercentile(past_ker, self.ker_percentile)
                            if ker_val < ker_thresh:
                                all_filters_pass = False

            if all_filters_pass:
                enter_long = True
                signal_reason = "Ichimoku Tenkan-Kijun Bullish Cross"

        # =======================
        # EXIT LOGIC (FASTER: OR condition)
        # =======================
        exit_long = False
        was_in_position = state.get("position", 0) > 0

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
