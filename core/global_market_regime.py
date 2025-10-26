"""
Global Market Regime System

This module implements a singleton pattern for market regime detection that calculates
the market regime ONCE using NIFTY data and provides it to all strategies.

This ensures consistent regime detection across all symbols and avoids redundant calculations.
"""

import pandas as pd

from .market_regime import MarketRegimeFilter, create_trend_following_filter


class GlobalMarketRegime:
    """
    Singleton class for global market regime detection.

    This class calculates market regime once using NIFTY data and caches results
    for all strategies to use consistently.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.nifty_data: pd.DataFrame | None = None
            self.market_filter: MarketRegimeFilter | None = None
            self.regime_cache: dict[str, bool] = {}
            self.is_enabled = False
            self._initialized = True

    def initialize(self) -> bool:
        """
        Initialize the global market regime system.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Load NIFTY data for market regime detection
            from data.loaders import load_nifty_data

            self.nifty_data = load_nifty_data()

            # Create market regime filter
            self.market_filter = create_trend_following_filter()

            self.is_enabled = True
            print("✅ Global Market Regime System initialized with NIFTY data")
            return True

        except ImportError as e:
            print(f"⚠️  Market regime system unavailable: {e}")
            self.is_enabled = False
            return False
        except Exception as e:
            print(f"⚠️  Could not initialize market regime system: {e}")
            self.is_enabled = False
            return False

    def should_trade(self, current_date: pd.Timestamp) -> bool:
        """
        Check if trading should be allowed on the given date.

        Lightweight version for fast backtesting.

        Args:
            current_date: Date to check market regime for

        Returns:
            True if trading is allowed (bullish regime), False otherwise
        """
        if not self.is_enabled or self.market_filter is None or self.nifty_data is None:
            return True  # Default to allowing trades if regime system is disabled

        try:
            # Normalize timestamp and create cache key
            normalized_date = pd.Timestamp(current_date).normalize()
            date_key = normalized_date.strftime("%Y-%m-%d")

            # Check cache first for maximum speed
            if date_key in self.regime_cache:
                return self.regime_cache[date_key]

            # Lightweight regime check - just use simple trend following
            # Get NIFTY data up to current date
            data_slice = self.nifty_data[self.nifty_data.index <= normalized_date]

            if len(data_slice) < 50:  # Need minimum data
                self.regime_cache[date_key] = True
                return True

            # Simple trend check: SMA20 > SMA50 = bullish
            recent_data = data_slice.tail(50)
            sma20 = recent_data["close"].rolling(20).mean().iloc[-1]
            sma50 = recent_data["close"].rolling(50).mean().iloc[-1]

            market_favorable = sma20 > sma50

            # Cache result
            self.regime_cache[date_key] = market_favorable

            return market_favorable

        except Exception:
            # Default to allowing trades on error
            self.regime_cache[date_key] = True
            return True

    def get_cache_stats(self) -> dict:
        """Get statistics about the regime cache."""
        return {
            "enabled": self.is_enabled,
            "cache_size": len(self.regime_cache),
            "nifty_data_rows": (
                len(self.nifty_data) if self.nifty_data is not None else 0
            ),
        }

    def clear_cache(self):
        """Clear the regime cache (useful for testing)."""
        self.regime_cache.clear()


# Global instance
global_market_regime = GlobalMarketRegime()


def initialize_global_market_regime() -> bool:
    """
    Initialize the global market regime system.

    Returns:
        True if successful, False otherwise
    """
    return global_market_regime.initialize()


def should_trade_today(current_date: pd.Timestamp) -> bool:
    """
    Check if trading should be allowed on the given date based on market regime.

    This is the main function that strategies should call.

    Args:
        current_date: Date to check

    Returns:
        True if trading is allowed (bullish market regime), False otherwise
    """
    return global_market_regime.should_trade(current_date)


def get_market_regime_stats() -> dict:
    """Get market regime system statistics."""
    return global_market_regime.get_cache_stats()
