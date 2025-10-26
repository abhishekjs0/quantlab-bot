"""
QuantLab Configuration System
============================

Centralized configuration for all system components.
Provides consistent paths, settings, and API configurations.

Author: QuantLab System
Date: 2025-10-19
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# ============================================================================
# PROJECT STRUCTURE
# ============================================================================

# Project root (where this config.py file is located)
PROJECT_ROOT = Path(__file__).parent

# Core directories
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CORE_DIR = PROJECT_ROOT / "core"
STRATEGIES_DIR = PROJECT_ROOT / "strategies"
RUNNERS_DIR = PROJECT_ROOT / "runners"
REPORTS_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"
VIZ_DIR = PROJECT_ROOT / "viz"
TESTS_DIR = PROJECT_ROOT / "tests"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

# Data files
BASKET_FILE = DATA_DIR / "basket.txt"  # Default fallback basket
SYMBOL_MAPPING_FILE = DATA_DIR / "dhan_symbol_mapping_comprehensive.csv"
SCRIP_MASTER_CSV = DATA_DIR / "api-scrip-master-detailed.csv"
SCRIP_MASTER_PARQUET = CACHE_DIR / "api-scrip-master-detailed.parquet"

# Basket files by size
BASKET_FILES = {
    "mega": DATA_DIR / "basket_mega.txt",  # ~72 stocks (5M+ volume)
    "large": DATA_DIR / "basket_large.txt",  # ~95 stocks (2.5M+ volume)
    "mid": DATA_DIR / "basket_mid.txt",  # ~51 stocks (500K+ volume)
    "small": DATA_DIR / "basket_small.txt",  # ~97 stocks (100K+ volume)
    "default": DATA_DIR / "basket.txt",  # Default basket file
}

# Default basket for backtests - uses basket.txt for backward compatibility
DEFAULT_BASKET_SIZE = "default"  # Run on default basket.txt by default

# Environment file
ENV_FILE = PROJECT_ROOT / ".env"


# ============================================================================
# API CONFIGURATION
# ============================================================================


@dataclass
class DhanConfig:
    """Dhan API configuration."""

    base_url: str = "https://api.dhan.co/v2"
    historical_endpoint: str = "charts/historical"
    fundlimit_endpoint: str = "fundlimit"
    rate_limit_seconds: float = 0.1
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class YFinanceConfig:
    """yfinance API configuration."""

    rate_limit_seconds: float = 0.5
    timeout_seconds: int = 30
    max_retries: int = 3
    suffix: str = ".NS"  # NSE suffix for Indian stocks


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================


@dataclass
class CacheConfig:
    """Cache management configuration."""

    expiry_days: int = 30
    cleanup_on_startup: bool = False
    max_cache_size_gb: float = 5.0
    enable_compression: bool = True
    metadata_enabled: bool = True


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_format: str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    console_enabled: bool = True
    file_enabled: bool = True
    max_file_size_mb: int = 10
    backup_count: int = 5


# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================


class QuantLabConfig:
    """Main configuration class for QuantLab system."""

    def __init__(self):
        """Initialize configuration with environment loading."""
        self.project_root = PROJECT_ROOT
        self.load_environment()

        # API configurations
        self.dhan = DhanConfig()
        self.yfinance = YFinanceConfig()

        # System configurations
        self.cache = CacheConfig()
        self.logging = LoggingConfig()

        # Environment variables
        self.dhan_credentials = self._load_dhan_credentials()

        # Ensure directories exist
        self._create_directories()

    def load_environment(self) -> None:
        """Load environment variables from .env file."""
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE, override=True)

    def _load_dhan_credentials(self) -> dict[str, str]:
        """Load and validate Dhan API credentials."""
        credentials = {
            "access_token": os.getenv("DHAN_ACCESS_TOKEN", ""),
            "client_id": os.getenv("DHAN_CLIENT_ID", ""),
            "api_key": os.getenv("DHAN_API_KEY", ""),
            "api_secret": os.getenv("DHAN_API_SECRET", ""),
        }
        return credentials

    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [
            DATA_DIR,
            CACHE_DIR,
            SCRIPTS_DIR,
            CORE_DIR,
            STRATEGIES_DIR,
            RUNNERS_DIR,
            REPORTS_DIR,
            DOCS_DIR,
            VIZ_DIR,
            TESTS_DIR,
            EXAMPLES_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, filename: str) -> Path:
        """Get full path for a cache file."""
        return CACHE_DIR / filename

    def get_data_path(self, filename: str) -> Path:
        """Get full path for a data file."""
        return DATA_DIR / filename

    def get_reports_path(self, filename: str) -> Path:
        """Get full path for a reports file."""
        return REPORTS_DIR / filename

    def get_basket_path(self, basket_size: str = None) -> Path:
        """
        Get basket file path based on size.

        Args:
            basket_size: Size of basket ('mega', 'large', 'mid', 'small', or None for default)

        Returns:
            Path to the basket file
        """
        if basket_size is None:
            basket_size = DEFAULT_BASKET_SIZE

        if basket_size in BASKET_FILES:
            basket_path = BASKET_FILES[basket_size]
            if basket_path.exists():
                return basket_path
            else:
                print(f"Warning: {basket_size} basket file not found: {basket_path}")
                print(f"Falling back to default basket: {BASKET_FILES['default']}")
                return BASKET_FILES["default"]
        else:
            print(
                f"Warning: Unknown basket size '{basket_size}'. Available: {list(BASKET_FILES.keys())}"
            )
            print(f"Using default basket: {BASKET_FILES['default']}")
            return BASKET_FILES["default"]

    def validate_dhan_credentials(self) -> bool:
        """Validate that required Dhan credentials are present."""
        required_fields = ["access_token", "client_id"]
        for field in required_fields:
            if not self.dhan_credentials.get(field):
                return False

        # Basic token format validation
        token = self.dhan_credentials["access_token"]
        if not token.startswith("eyJ") or len(token) < 200:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "project_root": str(self.project_root),
            "dhan": {
                "base_url": self.dhan.base_url,
                "rate_limit": self.dhan.rate_limit_seconds,
                "timeout": self.dhan.timeout_seconds,
            },
            "yfinance": {
                "rate_limit": self.yfinance.rate_limit_seconds,
                "timeout": self.yfinance.timeout_seconds,
                "suffix": self.yfinance.suffix,
            },
            "cache": {
                "expiry_days": self.cache.expiry_days,
                "max_size_gb": self.cache.max_cache_size_gb,
            },
            "paths": {
                "data": str(DATA_DIR),
                "cache": str(CACHE_DIR),
                "reports": str(REPORTS_DIR),
                "docs": str(DOCS_DIR),
            },
        }


# ============================================================================
# GLOBAL CONFIGURATION INSTANCE
# ============================================================================

# Global configuration instance
# Import this in other modules: from config import config
config = QuantLabConfig()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_symbol_cache_path(
    symbol: str, source: str = "dhan", security_id: int = None
) -> Path:
    """
    Get cache file path for a symbol.

    Args:
        symbol: Stock symbol
        source: Data source ('dhan' or 'yfinance')
        security_id: Dhan security ID (for dhan source)

    Returns:
        Path to cache file
    """
    if source == "dhan" and security_id:
        return CACHE_DIR / f"dhan_historical_{security_id}.csv"
    elif source == "yfinance":
        clean_symbol = symbol.replace("NSE:", "").replace(".NS", "").strip()
        return CACHE_DIR / f"yfinance_{clean_symbol}.csv"
    else:
        raise ValueError(f"Invalid source '{source}' or missing security_id for dhan")


def get_metadata_path(cache_path: Path) -> Path:
    """Get metadata file path for a cache file."""
    return cache_path.with_suffix(cache_path.suffix + "_metadata.json")


def get_basket_file(basket_size: str = None) -> Path:
    """
    Convenience function to get basket file path.

    Args:
        basket_size: Size of basket ('mega', 'large', 'mid', 'small', or None for default)

    Returns:
        Path to the basket file
    """
    if basket_size is None:
        basket_size = DEFAULT_BASKET_SIZE

    if basket_size in BASKET_FILES:
        basket_path = BASKET_FILES[basket_size]
        if basket_path.exists():
            return basket_path
        else:
            print(f"Warning: {basket_size} basket file not found: {basket_path}")
            print(f"Falling back to default basket: {BASKET_FILES['default']}")
            return BASKET_FILES["default"]
    else:
        print(
            f"Warning: Unknown basket size '{basket_size}'. Available: {list(BASKET_FILES.keys())}"
        )
        print(f"Using default basket: {BASKET_FILES['default']}")
        return BASKET_FILES["default"]


def get_available_baskets() -> dict[str, int]:
    """
    Get information about available baskets.

    Returns:
        Dictionary mapping basket size to number of symbols
    """
    baskets = {}
    for size, path in BASKET_FILES.items():
        if size == "default":
            continue
        if path.exists():
            with open(path) as f:
                symbol_count = len([line.strip() for line in f if line.strip()])
            baskets[size] = symbol_count
        else:
            baskets[size] = 0
    return baskets


def setup_logging(name: str = "quantlab") -> object:
    """
    Setup simple console logging for a module.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    import logging

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(getattr(logging, config.logging.level))

    # Console handler only (no file logging since we removed logs/)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(config.logging.format))
    logger.addHandler(console_handler)

    return logger


# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================


def validate_config() -> bool:
    """Validate the entire configuration."""
    try:
        # Check if essential directories exist
        essential_dirs = [PROJECT_ROOT, DATA_DIR, CACHE_DIR]
        for directory in essential_dirs:
            if not directory.exists():
                print(f"❌ Essential directory missing: {directory}")
                return False

        # Check if basket file exists
        if not BASKET_FILE.exists():
            print(f"⚠️ Basket file not found: {BASKET_FILE}")

        # Validate Dhan credentials if available
        if not config.validate_dhan_credentials():
            print("⚠️ Dhan credentials not properly configured")

        print("✅ Configuration validation passed")
        return True

    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    """Run configuration validation when script is executed directly."""
    print("🔧 QuantLab Configuration Validation")
    print("=" * 50)

    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Data Directory: {DATA_DIR}")
    print(f"Cache Directory: {CACHE_DIR}")
    print(f"Reports Directory: {REPORTS_DIR}")

    print("\n📋 Configuration Summary:")
    import json

    print(json.dumps(config.to_dict(), indent=2))

    print("\n🔍 Validation Results:")
    is_valid = validate_config()

    if is_valid:
        print("\n✅ System ready for use!")
    else:
        print("\n❌ Please fix configuration issues before proceeding.")
