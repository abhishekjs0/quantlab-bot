#!/usr/bin/env python3
"""
Weekly Rotation Strategy - Cross-Sectional Momentum/Mean Reversion

This strategy implements weekly rotation based on cross-sectional ranking:
- MOMENTUM: Buy top 10% performers (highest weekly returns)
- MEAN_REVERSION: Buy bottom 10% performers (lowest weekly returns)

Entry: Monday open (or first trading day of week)
Exit: Following Monday open (hold for 1 week)

The ranking is computed across ALL symbols in the basket, but the strategy
operates on individual symbols. It uses a pre-computed ranking cache that
must be populated before running the backtest.

FILTERS (applied on DAILY bars):
- MACD filter: MACD > Signal (12,26,9)
- EMA filter: Price > EMA(N) where N is configurable
"""
import json
import os
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, ClassVar
from pathlib import Path

from core.strategy import Strategy
from utils import EMA, MACD, ADX


# Path for persisting ranking cache (for multiprocessing compatibility)
_CACHE_FILE = Path(__file__).parent.parent / "cache" / "weekly_rotation_cache.json"


class WeeklyRotationStrategy(Strategy):
    """
    Weekly rotation strategy base class.
    
    Subclasses: WeeklyMomentumStrategy, WeeklyMeanReversionStrategy
    
    This strategy requires a ranking cache to be populated externally,
    which tells it which symbols to enter on which weeks.
    
    Due to multiprocessing, the cache is saved to a file and loaded by each worker.
    """
    
    # Class-level cache shared across all instances
    # Format: {(symbol, week_start_date): {"rank": float, "should_enter": bool}}
    _ranking_cache: ClassVar[Dict] = {}
    _weekly_returns: ClassVar[Dict] = {}  # {symbol: DataFrame with week_ending, pct_return}
    _cache_loaded: ClassVar[bool] = False
    
    # Mode: "momentum" (buy winners) or "mean_reversion" (buy losers)
    mode: str = "mean_reversion"
    select_pct: float = 10.0  # Top/bottom N% to select
    
    # Filter settings (only ADX filter kept)
    use_adx_filter: bool = False
    adx_period: int = 14
    adx_threshold: float = 25.0  # ADX > 25 = strong trend
    
    # Stop loss settings
    fixed_stop_pct: float = 0.10  # 10% fixed stop loss below entry
    use_trailing_stop: bool = False  # Trailing stop disabled
    trailing_stop_pct: float = 0.02  # 2% trailing stop below highest HIGH
    
    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides."""
        super().__init__()
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.name = f"Weekly {'Momentum' if self.mode == 'momentum' else 'Mean Reversion'}"
        self.description = (
            f"Weekly rotation: {'top' if self.mode == 'momentum' else 'bottom'} "
            f"{self.select_pct}% by weekly returns"
        )
        
        self._symbol = None
        self._week_entries = set()  # Set of week_start dates to enter
        
        # Load cache from file if not already loaded (for multiprocessing workers)
        self._ensure_cache_loaded()
    
    @classmethod
    def _ensure_cache_loaded(cls):
        """Load cache from file if not already loaded."""
        if cls._cache_loaded:
            return
        
        if _CACHE_FILE.exists():
            try:
                with open(_CACHE_FILE, "r") as f:
                    data = json.load(f)
                
                # Reconstruct cache with tuple keys
                cls._ranking_cache = {}
                for key_str, value in data.get("ranking_cache", {}).items():
                    # Key format: "SYMBOL|2024-01-15"
                    parts = key_str.split("|")
                    if len(parts) == 2:
                        symbol, date_str = parts
                        cls._ranking_cache[(symbol, pd.Timestamp(date_str))] = value
                
                cls._cache_loaded = True
            except Exception as e:
                print(f"Warning: Failed to load ranking cache: {e}")
    
    @classmethod
    def set_ranking_cache(cls, cache: Dict):
        """Set the pre-computed ranking cache and save to file."""
        cls._ranking_cache = cache
        cls._cache_loaded = True
        cls._save_cache_to_file()
    
    @classmethod
    def _save_cache_to_file(cls):
        """Save cache to file for multiprocessing workers."""
        try:
            # Create cache directory if needed
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert tuple keys to string keys for JSON
            serializable_cache = {}
            for (symbol, date), value in cls._ranking_cache.items():
                key_str = f"{symbol}|{date.strftime('%Y-%m-%d')}"
                serializable_cache[key_str] = value
            
            data = {"ranking_cache": serializable_cache}
            
            with open(_CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Warning: Failed to save ranking cache: {e}")
    
    @classmethod
    def set_weekly_returns(cls, returns: Dict):
        """Set weekly returns data for all symbols."""
        cls._weekly_returns = returns
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached data."""
        cls._ranking_cache = {}
        cls._weekly_returns = {}
        cls._cache_loaded = False
        
        # Remove cache file
        if _CACHE_FILE.exists():
            try:
                os.remove(_CACHE_FILE)
            except Exception:
                pass
    
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare indicators and identify entry weeks for this symbol."""
        self.data = df
        
        # Symbol will be set on first on_bar call from state
        # Can't compute entry weeks yet - will be done lazily
        self._week_entries_computed = False
        
        # Initialize indicators for filters
        self.initialize()
        
        return super().prepare(df)
    
    def initialize(self):
        """Initialize indicators for filters."""
        if len(self.data) < 30:
            return
        
        close = self.data["close"].values
        
        # ADX filter (only filter used)
        if self.use_adx_filter:
            high = self.data["high"].values
            low = self.data["low"].values
            adx_result = ADX(high, low, close, self.adx_period)
            self._adx = adx_result["adx"]
    
    def _compute_entry_weeks(self):
        """Identify which weeks this symbol should enter based on ranking cache."""
        self._week_entries = set()
        
        if not self._symbol:
            return
        
        # Look through ranking cache for this symbol
        for (symbol, week_start), info in self._ranking_cache.items():
            if symbol == self._symbol and info.get("should_enter", False):
                self._week_entries.add(pd.Timestamp(week_start))
        
        self._week_entries_computed = True
    
    def _get_week_start(self, ts: pd.Timestamp) -> pd.Timestamp:
        """Get the Monday of the week containing ts."""
        # Monday is weekday 0
        days_since_monday = ts.weekday()
        return (ts - pd.Timedelta(days=days_since_monday)).normalize()
    
    def _check_filters(self, idx: int, row) -> bool:
        """Check if all entry filters pass (only ADX filter)."""
        if idx < 1:
            return True
        
        # ADX filter: ADX > threshold (strong trend)
        if self.use_adx_filter and hasattr(self, '_adx'):
            if idx < len(self._adx):
                adx_val = self._adx[idx]
                if not np.isnan(adx_val):
                    if adx_val <= self.adx_threshold:
                        return False
        
        return True
    
    def _get_idx(self, ts) -> Optional[int]:
        """Get index for timestamp."""
        try:
            idx = self.data.index.get_loc(ts)
            if isinstance(idx, slice):
                idx = idx.start
            return idx
        except (KeyError, AttributeError):
            return None
    
    def on_entry(self, entry_time, entry_price, state) -> Dict[str, Any]:
        """
        Calculate initial stop loss on entry.
        Called when a trade is executed.
        
        Fixed stop = Entry price × (1 - 10%)
        Trailing stop = Highest HIGH × (1 - 2%)
        """
        # Fixed stop loss at entry - 10%
        fixed_stop = entry_price * (1 - self.fixed_stop_pct)
        
        # Initialize trailing stop tracking (use entry price as initial highest)
        state["entry_price"] = entry_price
        state["highest_high"] = entry_price  # Will be updated with actual HIGHs
        
        # Initial stop is the fixed stop (trailing stop will be updated in on_bar)
        return {"stop": fixed_stop}
    
    def on_bar(self, ts, row, state) -> Dict[str, Any]:
        """
        Generate entry/exit signals on each bar.
        
        Entry: First trading day of week if this symbol is in the selected set
        Exit: First trading day of next week (hold for ~1 week)
        
        Handles trading holidays: if Monday is a holiday, entry/exit on Tuesday.
        
        Stop Loss:
        - Fixed Stop: 10% below entry price (set in on_entry)
        - Trailing Stop: 2% below highest close (updated each bar)
        """
        result = {
            "enter_long": False,
            "exit_long": False,
            "signal_reason": "",
        }
        
        # Get symbol from state on first call and compute entry weeks
        if not self._symbol:
            self._symbol = state.get("symbol", "UNKNOWN")
            if not self._week_entries_computed:
                self._compute_entry_weeks()
            # Track which weeks we've already entered/exited to handle holidays
            self._weeks_entered = set()
            self._weeks_exited = set()
        
        try:
            idx = self.data.index.get_loc(ts)
            if isinstance(idx, slice):
                idx = idx.start
        except (KeyError, AttributeError):
            return result
        
        if idx is None or idx < 1:
            return result
        
        # Get position state
        qty = state.get("qty", 0)
        in_position = qty > 0
        current_high = float(row.get("high", 0))
        
        # ===== TRAILING STOP LOGIC (if enabled and in position) =====
        if self.use_trailing_stop and in_position and current_high > 0:
            entry_price = state.get("entry_price", current_high)
            highest_high = state.get("highest_high", current_high)
            
            # Update highest HIGH if current bar's high is higher
            if current_high > highest_high:
                highest_high = current_high
                state["highest_high"] = highest_high
            
            # Only activate trailing stop when stock has grown at least 2% from entry
            # This prevents the trailing stop from immediately tightening the fixed stop
            gain_from_entry = (highest_high - entry_price) / entry_price
            if gain_from_entry >= 0.02:  # 2% gain threshold to activate TSL
                # Calculate trailing stop: 2% below highest HIGH
                # Triggered when current bar's LOW < trailing_stop
                trailing_stop = highest_high * (1 - self.trailing_stop_pct)
                result["updated_stop"] = trailing_stop
        
        # Get week info (ISO week - Monday is day 0)
        week_start = self._get_week_start(ts)
        current_week_id = (ts.isocalendar().year, ts.isocalendar().week)
        
        # Check if this is the first trading day of the week
        # by looking at the previous bar's week
        prev_ts = self.data.index[idx - 1] if idx > 0 else None
        prev_week_id = (prev_ts.isocalendar().year, prev_ts.isocalendar().week) if prev_ts else None
        is_first_day_of_week = (prev_week_id != current_week_id) if prev_week_id else True
        
        # ===== CHECK IF SYMBOL SHOULD BE HELD THIS WEEK =====
        # If symbol is in this week's selection and passes filters, it should be held
        should_hold_this_week = False
        if is_first_day_of_week and week_start in self._week_entries:
            if self._check_filters(idx - 1, self.data.iloc[idx - 1]):  # Use t-1 bar
                should_hold_this_week = True
        
        # ===== EXIT LOGIC =====
        # Exit on first trading day of week ONLY if:
        # 1. We're in a position AND
        # 2. This symbol is NOT selected for this week (or doesn't pass filters)
        if in_position and is_first_day_of_week:
            if current_week_id not in self._weeks_exited:
                if not should_hold_this_week:
                    # Symbol not selected this week - exit
                    self._weeks_exited.add(current_week_id)
                    result["exit_long"] = True
                    result["signal_reason"] = "Weekly rotation exit"
                else:
                    # Symbol selected again - continue holding, reset trailing stop tracking
                    state["highest_high"] = state.get("entry_price", current_high)
                    result["signal_reason"] = "Continuing to hold (re-selected)"
        
        # ===== ENTRY LOGIC =====
        # Entry on first trading day of week if:
        # 1. Not in position AND
        # 2. This symbol is selected for this week AND passes filters
        if not in_position and is_first_day_of_week:
            if current_week_id not in self._weeks_entered:
                if should_hold_this_week:
                    self._weeks_entered.add(current_week_id)
                    result["enter_long"] = True
                    result["signal_reason"] = f"Weekly rotation entry ({self.mode})"
        
        return result


class WeeklyMomentumStrategy(WeeklyRotationStrategy):
    """Buy top N% performers (momentum)."""
    mode = "momentum"
    
    def __init__(self, **kwargs):
        kwargs["mode"] = "momentum"
        super().__init__(**kwargs)


class WeeklyMeanReversionStrategy(WeeklyRotationStrategy):
    """Buy bottom N% performers (mean reversion)."""
    mode = "mean_reversion"
    
    def __init__(self, **kwargs):
        kwargs["mode"] = "mean_reversion"
        super().__init__(**kwargs)


# =============================================================================
# HELPER FUNCTIONS FOR PRE-COMPUTING RANKINGS
# =============================================================================

def compute_weekly_returns(daily_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Compute weekly returns for all symbols.
    
    Weekly return = (Friday close - Monday open) / Monday open
    This measures the full trading week performance from Monday open to Friday close.
    
    Args:
        daily_data: Dict of symbol -> DataFrame with OHLC daily data
    
    Returns:
        Dict of symbol -> DataFrame with columns: week_ending, week_start, pct_return
    """
    weekly_returns = {}
    
    for symbol, df in daily_data.items():
        if df is None or df.empty:
            continue
        
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        df = df.copy()
        df.columns = df.columns.str.lower()
        
        # Add week identifiers
        df["year"] = df.index.isocalendar().year
        df["week"] = df.index.isocalendar().week
        df["week_id"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)
        
        weekly_data = []
        for week_id, week_df in df.groupby("week_id"):
            if len(week_df) < 2:
                continue
            
            open_price = week_df["open"].iloc[0]
            close_price = week_df["close"].iloc[-1]
            pct_return = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
            
            weekly_data.append({
                "week_ending": week_df.index[-1],
                "week_start": week_df.index[0],
                "pct_return": pct_return,
            })
        
        if weekly_data:
            weekly_returns[symbol] = pd.DataFrame(weekly_data)
    
    return weekly_returns


def compute_ranking_cache(
    weekly_returns: Dict[str, pd.DataFrame],
    mode: str = "mean_reversion",
    select_pct: float = 10.0,
    min_drop_pct: float = 0.0,
    nifty_weekly: Optional[pd.DataFrame] = None,
    require_nifty_down: bool = False,
) -> Dict:
    """
    Pre-compute which symbols to enter on which weeks.
    
    Args:
        weekly_returns: Dict from compute_weekly_returns()
        mode: "momentum" (top performers) or "mean_reversion" (bottom performers)
        select_pct: Top/bottom N% to select
        min_drop_pct: Minimum drop % required (e.g., 5.0 = only stocks down >5%)
        nifty_weekly: DataFrame with NIFTY weekly returns (week_ending, pct_return)
        require_nifty_down: If True, only enter when NIFTY was down that week
    
    Returns:
        Dict of {(symbol, week_start): {"rank": float, "should_enter": bool}}
    """
    cache = {}
    
    # Build NIFTY return lookup
    nifty_lookup = {}
    if nifty_weekly is not None:
        for _, row in nifty_weekly.iterrows():
            nifty_lookup[row["week_ending"]] = row["pct_return"]
    
    # Collect all unique weeks
    all_weeks = set()
    for symbol, df in weekly_returns.items():
        for _, row in df.iterrows():
            all_weeks.add(row["week_ending"])
    
    # For each week, rank all symbols and select top/bottom N%
    for week_ending in sorted(all_weeks):
        # STEP 1: Check NIFTY filter - skip week if NIFTY was UP
        if require_nifty_down:
            nifty_ret = nifty_lookup.get(week_ending, 0)
            if nifty_ret >= 0:
                # NIFTY was up - skip this week entirely
                continue
        
        # Get returns for this week for all symbols
        week_returns = []
        for symbol, df in weekly_returns.items():
            week_row = df[df["week_ending"] == week_ending]
            if not week_row.empty:
                week_returns.append({
                    "symbol": symbol,
                    "pct_return": week_row.iloc[0]["pct_return"],
                    "week_start": week_row.iloc[0]["week_start"],
                })
        
        if not week_returns:
            continue
        
        # Sort by return (ascending = worst performers first)
        week_returns.sort(key=lambda x: x["pct_return"])
        
        # STEP 2: Select top or bottom N% FIRST (before min_drop filter)
        n_select = max(1, int(len(week_returns) * select_pct / 100))
        
        if mode == "mean_reversion":
            # Bottom N% (lowest returns = oversold = buy for reversion)
            selected = week_returns[:n_select]
        else:
            # Top N% (highest returns = momentum = ride the trend)
            selected = week_returns[-n_select:]
        
        # STEP 3: From selected B20%, filter those that fell > min_drop_pct
        if mode == "mean_reversion" and min_drop_pct > 0:
            selected = [x for x in selected if x["pct_return"] <= -min_drop_pct]
            if not selected:
                continue
        
        selected_symbols = {x["symbol"] for x in selected}
        
        # Store in cache - use NEXT week's start as entry point
        # (we see this week's performance, enter next week)
        next_week_start = week_ending + pd.Timedelta(days=1)
        # Adjust to Monday
        while next_week_start.weekday() != 0:
            next_week_start += pd.Timedelta(days=1)
        
        for item in week_returns:
            symbol = item["symbol"]
            cache[(symbol, next_week_start)] = {
                "rank": item["pct_return"],
                "should_enter": symbol in selected_symbols,
            }
    
    return cache
