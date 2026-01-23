"""
Weekly BB Mean Reversion - 2-Step 30% Scale-In Strategy
========================================================

Pyramid mean reversion:
1. First entry (50%): Daily green candle opens below weekly BB lower
2. Scale-in (50%): If drops 30% AND still below BB lower
3. Exit: Weekly SMA touch OR 30% SL from scale-in

Entry Filters:
- Daily green candle with bigger body than prev day
- Open < weekly lower BB
- NIFTY200 > its 200 EMA (market regime filter)

Exit:
- TP: Daily high touches weekly SMA
- SL: 30% below scale-in fill price
- Force exit: Scale trigger but NOT below BB lower

IMPORTANT: Run on DAILY (1d) data, strategy resamples to weekly
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

from core.strategy import Strategy
from utils.indicators import BollingerBands
from core.loaders import load_nifty200


class BBPyramid30Pct(Strategy):
    """Weekly BB Mean Reversion with 2-step 30% pyramid scale-in."""

    pyramiding = 2          # Allow 2 entries: first + scale-in
    bb_period = 20          # Weekly SMA period for BB + TP
    bb_sd = 2.0             # Standard deviation multiplier
    sl_pct = 0.30           # 30% SL from scale-in fill
    scale_drop_pct = 0.30   # 30% drop triggers scale-in check
    min_price = 1.0         # Minimum price filter

    # Internal state
    _weekly_data = None
    _daily_to_week_map = None
    _first_fill_price = None
    _scaled_in = False
    _scale_fill_price = None
    _nifty200_ema200 = None

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and calculate indicators."""
        self.data = df.copy()
        
        # Load and calculate NIFTY200 200 EMA
        self._calculate_nifty200_filter()
        
        # Resample daily to weekly and calculate BB
        self._build_weekly_data()
        self._calculate_weekly_indicators()
        self._map_daily_to_weekly()
        
        # Indicator for plotting
        self.weekly_sma_daily = self.I(
            lambda: self._get_daily_sma_values(),
            name=f"Weekly SMA({self.bb_period})",
            overlay=True,
            color="blue"
        )
        
        return super().prepare(df)

    def _calculate_nifty200_filter(self):
        """Calculate NIFTY200 > 200 EMA filter."""
        try:
            nifty200_df = load_nifty200()
            
            if nifty200_df is None or nifty200_df.empty:
                self.data['nifty200_above_ema200'] = True
                return
            
            # Calculate 200 EMA
            from utils.indicators import EMA
            nifty200_close = nifty200_df['close'].values
            ema200 = EMA(nifty200_close, 200)
            nifty200_df['ema200'] = ema200
            nifty200_df['above_ema200'] = nifty200_close > ema200
            
            # Create mapping: both indices should be timezone-naive date-only
            # NIFTY200 index is already timezone-naive from loader
            # Stock data index from backtesting.py is also timezone-naive
            nifty200_series = pd.Series(
                nifty200_df['above_ema200'].values,
                index=nifty200_df.index
            )
            
            # Map NIFTY200 values to stock dates (forward fill for weekends/holidays)
            mapped_values = self.data.index.map(lambda d: nifty200_series.get(d, pd.NA))
            temp_series = pd.Series(mapped_values, index=self.data.index)
            temp_series = temp_series.infer_objects(copy=False)  # Handle FutureWarning before operations
            temp_series = temp_series.ffill()
            temp_series = temp_series.fillna(True)  # Default to True if no data
            self.data['nifty200_above_ema200'] = temp_series.astype(bool)
            
        except Exception as e:
            # Default to True if data unavailable
            print(f"EXCEPTION in filter: {e}")
            import traceback
            traceback.print_exc()
            self.data['nifty200_above_ema200'] = True

    def _build_weekly_data(self):
        """Resample daily to weekly (Monday-Friday)."""
        df = self.data.copy().set_index(self.data.index)
        
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
        """Calculate weekly Bollinger Bands."""
        close = self._weekly_data['close'].values
        bb = BollingerBands(close, n=self.bb_period, std=self.bb_sd)
        
        self._weekly_data['bb_lower'] = bb['lower']
        self._weekly_data['bb_upper'] = bb['upper']
        self._weekly_data['sma'] = bb['middle']

    def _map_daily_to_weekly(self):
        """Map daily dates to weekly BB values (no lookahead)."""
        weekly = self._weekly_data.copy()
        daily = pd.DataFrame({'date': self.data.index}).reset_index(drop=True)
        daily['date'] = pd.to_datetime(daily['date'])
        weekly['week_end'] = pd.to_datetime(weekly['week_end'])
        
        merged = pd.merge_asof(
            daily.sort_values('date'),
            weekly[['week_end', 'bb_lower', 'sma']].sort_values('week_end'),
            left_on='date',
            right_on='week_end',
            direction='backward'
        )
        
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
        """Set initial state on entry."""
        if entry_price is None or entry_price <= 0:
            return {}
        
        # Track first fill or scale-in fill
        if self._first_fill_price is None:
            # First entry
            self._first_fill_price = entry_price
            self._scaled_in = False
            return {}
        else:
            # This is a scale-in (second entry)
            self._scaled_in = True
            self._scale_fill_price = entry_price
            # Set stop loss at 30% below scale-in price
            stop_loss = entry_price * (1 - self.sl_pct)
            return {"stop": stop_loss}
        
        return {}
    
    def on_exit(self, exit_time, exit_price, state) -> Dict[str, Any]:
        """Reset position tracking on exit."""
        self._first_fill_price = None
        self._scaled_in = False
        self._scale_fill_price = None
        return {}

    def on_bar(self, ts, row, state) -> Dict[str, Any]:
        """Trading logic executed on each bar."""
        result = {
            "enter_long": False,
            "exit_long": False,
            "signal_reason": "",
            "size": state.get("broker_config", {}).get("qty_pct_of_equity", 0.05),
        }
        
        qty = state.get("qty", 0)
        in_position = qty > 0
        
        # Reset state if position closed
        if not in_position and self._first_fill_price is not None:
            self._first_fill_price = None
            self._scaled_in = False
            self._scale_fill_price = None
        
        # Get previous day's data (no lookahead)
        idx = self.data.index.get_loc(ts)
        if isinstance(idx, slice):
            idx = idx.start
        if idx == 0:
            return result
        
        prev_row = self.data.iloc[idx - 1]
        
        # Price and market filter (enter when NIFTY200 is BELOW 200 EMA - weak market for mean reversion)
        price_ok = (row.open >= self.min_price) and (row.close >= self.min_price)
        
        # Check NIFTY200 filter: enter only when market is below 200 EMA (weak market favors mean reversion)
        # Default to blocking entry if column doesn't exist or value is missing
        market_ok = False
        if 'nifty200_above_ema200' in self.data.columns:
            try:
                above_ema = bool(self.data.loc[ts, 'nifty200_above_ema200'])
                market_ok = not above_ema  # True when below EMA (allows entry), False when above (blocks)
            except:
                market_ok = False  # Block on any error
        
        # ===== FIRST ENTRY (50% position) =====
        if not in_position and price_ok and market_ok:
            weekly_bb_lower = self._daily_to_week_map['bb_lower'].get(ts)
            
            if weekly_bb_lower is None or pd.isna(weekly_bb_lower):
                return result
            
            # Entry conditions
            is_green = row.close > row.open
            opens_below_bb = row.open < weekly_bb_lower
            body = abs(row.close - row.open)
            prev_body = abs(prev_row['close'] - prev_row['open'])
            bigger_body = body > prev_body
            
            if is_green and opens_below_bb and bigger_body:
                result["enter_long"] = True
                result["size"] = state.get("broker_config", {}).get("qty_pct_of_equity", 0.05)
                result["signal_reason"] = "First Entry (Green candle below BB)"
        
        # ===== SCALE-IN (additional 50%) =====
        elif in_position and not self._scaled_in and price_ok:
            if self._first_fill_price is not None:
                scale_trigger = self._first_fill_price * (1.0 - self.scale_drop_pct)
                scale_hit = row.low <= scale_trigger
                
                if scale_hit:
                    weekly_bb_lower = self._daily_to_week_map['bb_lower'].get(ts)
                    below_lower_bb = (weekly_bb_lower is not None and 
                                    not pd.isna(weekly_bb_lower) and 
                                    row.close < weekly_bb_lower)
                    
                    if below_lower_bb:
                        result["enter_long"] = True
                        result["size"] = state.get("broker_config", {}).get("qty_pct_of_equity", 0.05)
                        result["signal_reason"] = "Scale-in (30% drop, still below BB)"
                    else:
                        result["exit_long"] = True
                        result["signal_reason"] = "Exit: Scale trigger but not below BB"
        
        # ===== EXIT (TP check) =====
        if in_position:
            weekly_sma = self._daily_to_week_map['sma'].get(ts)
            
            if weekly_sma is not None and not np.isnan(weekly_sma):
                if row.high >= weekly_sma:
                    result["exit_long"] = True
                    result["signal_reason"] = "TP: Weekly SMA Touch"
        
        return result
