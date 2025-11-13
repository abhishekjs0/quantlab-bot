import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ADX, ATR, EMA, MFI, RSI, VWAP


class CandlestickPatternsStrategy(Strategy):
    """The Whale - 20+ bullish candlestick patterns with confluence filters."""

    small_body_pct = 0.30
    long_body_pct = 0.60
    doji_pct = 5.0
    atr_period = 14
    take_profit_pct = 0.10
    stop_loss_atr_mult = 1.0
    trailing_stop_pct = 0.006  # 0.6% of entry price as TSL distance

    # Confluence filters
    # NOTE: Toggle these to run baseline vs filtered backtests. Baseline = all False.
    use_adx_filter = True  # ADX > 20 (trend strength)
    use_ema_filter = True  # EMA50 > EMA200 (bullish alignment)
    use_rsi_filter = True  # RSI (40-70) (momentum zone)
    use_volume_filter = True  # Volume > 5-bar average
    use_vwap_filter = True  # Close > VWAP (price above average value)
    use_mfi_filter = True  # MFI (20-80) (money flow)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators for confluence filters."""
        self.atr = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

        # ADX for trend strength (>20 = strong trend)
        adx_result = ADX(
            self.data.high.values.astype(float),
            self.data.low.values.astype(float),
            self.data.close.values.astype(float),
            9,
        )
        self.adx = adx_result.get("adx", np.zeros(len(self.data)))

        # EMAs for bullish alignment
        self.ema50 = EMA(self.data.close.values.astype(float), 50)
        self.ema200 = EMA(self.data.close.values.astype(float), 200)

        # RSI for momentum zone (40-70)
        self.rsi = RSI(self.data.close, 21)

        # Volume for confirmation
        self.volume = (
            self.data.volume.values.astype(float)
            if "volume" in self.data.columns
            else np.ones(len(self.data))
        )

        # VWAP for price above average value
        vwap_result = VWAP(
            self.data.high.values.astype(float),
            self.data.low.values.astype(float),
            self.data.close.values.astype(float),
            self.volume,
        )
        self.vwap = (
            vwap_result
            if isinstance(vwap_result, np.ndarray)
            else np.zeros(len(self.data))
        )

        # MFI for money flow (20-80)
        mfi_result = MFI(
            self.data.high.values.astype(float),
            self.data.low.values.astype(float),
            self.data.close.values.astype(float),
            self.volume,
            21,
        )
        self.mfi = (
            mfi_result
            if isinstance(mfi_result, np.ndarray)
            else np.zeros(len(self.data))
        )

    def _get_idx(self, ts):
        """Get bar index from timestamp."""
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                return idx_result.start
            return idx_result
        except (KeyError, AttributeError):
            return None

    def _check_confluence_filters(self, idx):
        """Check all confluence filters for entry.

        All filters must PASS (return True means all filters OK):
        ✅ ADX > 20 - Trend strength confirmation
        ✅ EMA50 > EMA200 - Bullish alignment
        ✅ RSI (40-70) - Momentum zone
        ✅ Volume > 5-bar avg - Volume confirmation
        ✅ Close > VWAP - Price above average value
        ✅ MFI (20-80) - Money flow zone
        """
        if idx < 50:  # Need enough data for all indicators
            return False

        try:
            row = self.data.iloc[idx]
            close = float(row.get("close", 0))
            current_vol = float(row.get("volume", 0))

            filters_status = {}

            # RETURN FALSE if ANY filter FAILS
            # RETURN TRUE only if ALL filters PASS (or are disabled)

            # ADX Filter: Require ADX > 20
            if self.use_adx_filter:
                adx_val = float(self.adx[idx]) if np.isfinite(self.adx[idx]) else 0
                adx_pass = adx_val > 20
                filters_status["ADX"] = (adx_val, adx_pass)
                if not adx_pass:  # If filter FAILS
                    return False

            # EMA Filter: Require EMA50 > EMA200
            if self.use_ema_filter:
                ema50_val = (
                    float(self.ema50[idx]) if np.isfinite(self.ema50[idx]) else 0
                )
                ema200_val = (
                    float(self.ema200[idx]) if np.isfinite(self.ema200[idx]) else 0
                )
                ema_pass = ema50_val > ema200_val
                filters_status["EMA"] = (ema50_val, ema200_val, ema_pass)
                if not ema_pass:  # If filter FAILS
                    return False

            # RSI Filter: Require 40 <= RSI <= 70
            if self.use_rsi_filter:
                rsi_val = float(self.rsi[idx]) if np.isfinite(self.rsi[idx]) else 50
                rsi_pass = 40 <= rsi_val <= 70
                filters_status["RSI"] = (rsi_val, rsi_pass)
                if not rsi_pass:  # If filter FAILS
                    return False

            # Volume Filter: Require volume > 5-bar average
            if self.use_volume_filter:
                start_idx = max(0, idx - 4)
                avg_vol = np.mean(self.volume[start_idx : idx + 1])
                vol_pass = current_vol > avg_vol
                filters_status["Volume"] = (current_vol, avg_vol, vol_pass)
                if not vol_pass:  # If filter FAILS
                    return False

            # VWAP Filter: Require close > VWAP
            if self.use_vwap_filter:
                vwap_val = float(self.vwap[idx]) if np.isfinite(self.vwap[idx]) else 0
                vwap_pass = close > vwap_val
                filters_status["VWAP"] = (close, vwap_val, vwap_pass)
                if not vwap_pass:  # If filter FAILS
                    return False

            # MFI Filter: Require 20 <= MFI <= 80
            if self.use_mfi_filter:
                mfi_val = float(self.mfi[idx]) if np.isfinite(self.mfi[idx]) else 50
                mfi_pass = 20 <= mfi_val <= 80
                filters_status["MFI"] = (mfi_val, mfi_pass)
                if not mfi_pass:  # If filter FAILS
                    return False

            # DEBUG: Log filter results (remove after debugging)
            import sys

            if hasattr(self, "_debug_filters") and self._debug_filters:
                print(
                    f"[DEBUG] idx={idx} Filters PASSED: {filters_status}",
                    file=sys.stderr,
                )

            # All filters passed (or none enabled)
            return True

        except (IndexError, KeyError, ValueError, TypeError):
            return False

    def _candle(self, idx):
        """Extract candle properties."""
        if idx < 0 or idx >= len(self.data):
            return None

        try:
            row = self.data.iloc[idx]
            o, h, l, c = (
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
            )

            if not all(np.isfinite([o, h, l, c])):
                return None

            rng = h - l
            if rng <= 0:
                return None

            body = abs(c - o)
            body_hi = max(c, o)
            body_lo = min(c, o)
            up_shadow = h - body_hi
            dn_shadow = body_lo - l

            return {
                "o": o,
                "h": h,
                "l": l,
                "c": c,
                "rng": rng,
                "body": body,
                "body_hi": body_hi,
                "body_lo": body_lo,
                "up_shadow": up_shadow,
                "dn_shadow": dn_shadow,
                "is_white": c > o,
                "is_black": c < o,
                "is_small": body < rng * self.small_body_pct,
                "is_long": body > rng * self.long_body_pct,
                "is_doji": body < rng * (self.doji_pct / 100),
            }
        except (IndexError, KeyError, ValueError, TypeError):
            return None

    def _detect_pattern(self, idx):
        """Detect any bullish candlestick pattern."""
        if idx < 4:
            return None

        patterns = [
            ("Engulfing", self._engulfing),
            ("Harami", self._harami),
            ("Piercing", self._piercing),
            ("Morning Star", self._morning_star),
            ("Morning Doji Star", self._morning_doji_star),
            ("Hammer", self._hammer),
            ("Inverted Hammer", self._inverted_hammer),
            ("Dragonfly Doji", self._dragonfly_doji),
            ("Gravestone Doji", self._gravestone_doji),
            ("Abandoned Baby", self._abandoned_baby),
            ("Kicker", self._kicker),
            ("Belt Hold", self._belt_hold),
            ("Homing Pigeon", self._homing_pigeon),
            ("Matching Low", self._matching_low),
        ]

        for name, detector in patterns:
            if detector(idx):
                return name
        return None

    def _hammer(self, idx):
        """1 candle: small white body, long lower shadow."""
        c = self._candle(idx)
        if not c or not c["is_white"] or not c["is_small"]:
            return False
        return c["dn_shadow"] >= c["body"] * 2 and c["up_shadow"] < c["body"] * 0.5

    def _inverted_hammer(self, idx):
        """1 candle: small white body, long upper shadow."""
        c = self._candle(idx)
        if not c or not c["is_white"] or not c["is_small"]:
            return False
        return c["up_shadow"] >= c["body"] * 2 and c["dn_shadow"] < c["body"] * 0.5

    def _belt_hold(self, idx):
        """1 candle: small white body at high."""
        c = self._candle(idx)
        if not c or not c["is_white"] or not c["is_small"]:
            return False
        return c["dn_shadow"] >= c["body"] * 2 and c["up_shadow"] < c["body"] * 0.5

    def _dragonfly_doji(self, idx):
        """1 candle: doji with long lower shadow."""
        c = self._candle(idx)
        if not c or not c["is_doji"]:
            return False
        return c["dn_shadow"] > c["rng"] * 0.5 and c["up_shadow"] < c["rng"] * 0.1

    def _gravestone_doji(self, idx):
        """1 candle: doji with long upper shadow."""
        c = self._candle(idx)
        if not c or not c["is_doji"]:
            return False
        return c["up_shadow"] > c["rng"] * 0.5 and c["dn_shadow"] < c["rng"] * 0.1

    def _engulfing(self, idx):
        """2 candles: white engulfs black."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c2["is_white"]:
            return c2["o"] <= c1["c"] and c2["c"] >= c1["o"]
        return False

    def _harami(self, idx):
        """2 candles: small white inside large black."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c1["is_long"] and c2["is_white"] and c2["is_small"]:
            return c2["h"] <= c1["body_hi"] and c2["l"] >= c1["body_lo"]
        return False

    def _piercing(self, idx):
        """2 candles: black long, white opens gap down, closes >50% body."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c1["is_long"] and c2["is_white"]:
            body_mid = c1["body_lo"] + c1["body"] / 2
            return c2["o"] < c1["l"] and c2["c"] > body_mid and c2["c"] < c1["o"]
        return False

    def _kicker(self, idx):
        """2 candles: black to white with gap up."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c2["is_white"]:
            return c2["l"] > c1["h"]
        return False

    def _homing_pigeon(self, idx):
        """2 candles: both black, second inside first."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c2["is_black"]:
            return c2["h"] < c1["body_hi"] and c2["l"] > c1["body_lo"]
        return False

    def _matching_low(self, idx):
        """2 candles: similar close price."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_black"] and c2["is_white"]:
            return abs(c1["c"] - c2["c"]) < c1["rng"] * 0.05
        return False

    def _morning_star(self, idx):
        """3 candles: black long, small, white closes above mid."""
        if idx < 2:
            return False
        c1 = self._candle(idx - 2)
        c2 = self._candle(idx - 1)
        c3 = self._candle(idx)
        if not all([c1, c2, c3]):
            return False
        if c1["is_black"] and c1["is_long"] and c2["is_small"] and c3["is_white"]:
            body_mid = c1["body_lo"] + c1["body"] / 2
            return c2["h"] < c1["l"] and c3["c"] > body_mid
        return False

    def _morning_doji_star(self, idx):
        """3 candles: black, doji gaps down, white."""
        if idx < 2:
            return False
        c1 = self._candle(idx - 2)
        c2 = self._candle(idx - 1)
        c3 = self._candle(idx)
        if not all([c1, c2, c3]):
            return False
        if c1["is_black"] and c2["is_doji"] and c3["is_white"]:
            return c2["h"] < c1["l"] and c3["c"] > c1["body_lo"] + c1["body"] / 2
        return False

    def _abandoned_baby(self, idx):
        """3 candles: black, doji gaps down, white gaps up."""
        if idx < 2:
            return False
        c1 = self._candle(idx - 2)
        c2 = self._candle(idx - 1)
        c3 = self._candle(idx)
        if not all([c1, c2, c3]):
            return False
        if c1["is_black"] and c2["is_doji"] and c3["is_white"]:
            return c2["h"] < c1["l"] and c3["l"] > c2["h"]
        return False

    def _bearish_engulfing(self, idx):
        """2 candles: black engulfs white."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_white"] and c2["is_black"]:
            return c2["o"] >= c1["c"] and c2["c"] <= c1["o"]
        return False

    def _bearish_harami(self, idx):
        """2 candles: small black inside large white."""
        if idx < 1:
            return False
        c1 = self._candle(idx - 1)
        c2 = self._candle(idx)
        if not c1 or not c2:
            return False
        if c1["is_white"] and c1["is_long"] and c2["is_black"] and c2["is_small"]:
            return c2["h"] <= c1["body_hi"] and c2["l"] >= c1["body_lo"]
        return False

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate stop loss and take profit on entry.
        Called when a trade is executed.
        """
        idx = self._get_idx(entry_time)
        if idx is None or idx < 0 or idx >= len(self.atr):
            return {}

        atr_val = self.atr[idx]
        if not np.isfinite(atr_val) or atr_val <= 0:
            return {}

        # Initial stop loss at entry - 1x ATR
        stop = entry_price - (atr_val * self.stop_loss_atr_mult)

        # Take profit at entry + 10%
        take_profit = entry_price * (1 + self.take_profit_pct)

        # Initialize end-of-day TSL state for this trade
        state["entry_price"] = entry_price
        state["highest_close"] = entry_price  # Start with entry price
        state["tsl_stop"] = stop  # Start with initial SL

        return {
            "stop": stop,
            "take_profit": take_profit,
        }

    def on_bar(self, ts, row, state):
        """
        Execute trading logic each bar (daily).

        Entry: Signal on current bar → Execute at NEXT bar's open
        Exit: Bearish pattern or take profit/stop loss

        TSL (End-of-Day): Calculated at day's close using highest close reached
        - At each day's close, update TSL = highest_close - (0.6% × entry_price)
        - TSL can only move up (never down)
        - Next day's open will check if TSL was breached
        """
        idx = self._get_idx(ts)
        if idx is None or idx < 4:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        if not np.isfinite(self.atr[idx]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        current_close = float(row.get("close", 0))

        # ===== END-OF-DAY TSL CALCULATION =====
        # If in position, update TSL at day's close
        if state.get("qty", 0) > 0:
            entry_price = state.get("entry_price")
            highest_close = state.get("highest_close", entry_price)

            if entry_price and highest_close:
                # Track highest close reached so far
                highest_close = max(highest_close, current_close)
                state["highest_close"] = highest_close

                # Calculate TSL: highest close - (0.6% of entry price)
                tsl_value = entry_price * self.trailing_stop_pct
                new_tsl = highest_close - tsl_value

                # TSL can only move up (never down)
                current_tsl = state.get(
                    "tsl_stop", entry_price - (entry_price * self.stop_loss_atr_mult)
                )
                if new_tsl > current_tsl:
                    state["tsl_stop"] = new_tsl
                    # Return updated stop for next bar
                    result = {
                        "enter_long": False,
                        "exit_long": False,
                        "updated_stop": new_tsl,
                    }
                else:
                    result = {"enter_long": False, "exit_long": False}
            else:
                result = {"enter_long": False, "exit_long": False}
        else:
            result = {"enter_long": False, "exit_long": False}

        # ===== EXIT LOGIC (if in position) =====
        if state.get("qty", 0) > 0:
            # Check for bearish patterns (exit signals)
            if self._bearish_engulfing(idx):
                return {
                    "enter_long": False,
                    "exit_long": True,
                    "signal_reason": "Bearish Engulfing",
                }
            if self._bearish_harami(idx):
                return {
                    "enter_long": False,
                    "exit_long": True,
                    "signal_reason": "Bearish Harami",
                }

            # Return TSL update (if any) or continue holding
            return result

        # ===== ENTRY LOGIC (if NOT in position) =====
        # Detect bullish patterns with confluence filters
        pattern = self._detect_pattern(idx)
        if pattern:
            # Check all confluence filters
            if self._check_confluence_filters(idx):
                # All filters passed - Entry signal on current bar
                # Engine will execute at NEXT bar's open (execute_on_next_open=True)
                return {
                    "enter_long": True,
                    "signal_reason": pattern,
                }

        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
