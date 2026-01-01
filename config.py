"""Root configuration for QuantLab workspace."""

from pathlib import Path

# Base directory of the workspace
WORKSPACE_DIR = Path(__file__).parent

# Reports directory
REPORTS_DIR = WORKSPACE_DIR / "reports"

# Data directory
DATA_DIR = WORKSPACE_DIR / "data"

# Cache directory for downloaded data
CACHE_DIR = DATA_DIR / "cache"

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Basket configuration - baskets now in data/baskets/ folder
BASKETS_DIR = DATA_DIR / "baskets"
DEFAULT_BASKET_SIZE = "test"

BASKET_FILES = {
    "test": BASKETS_DIR / "basket_test.txt",
    "small": BASKETS_DIR / "basket_small.txt",
    "mid": BASKETS_DIR / "basket_mid.txt",
    "large": BASKETS_DIR / "basket_large.txt",
    "mega": BASKETS_DIR / "basket_mega.txt",
    "main": BASKETS_DIR / "basket_main.txt",
    "default": BASKETS_DIR / "basket_test.txt",
}


def get_basket_file(basket_name: str) -> Path:
    """Get basket file path by name."""
    return BASKET_FILES.get(basket_name, BASKET_FILES["default"])


def get_available_baskets() -> dict[str, int]:
    """Get available baskets with their stock counts."""
    baskets = {}
    for name, path in BASKET_FILES.items():
        if path.exists():
            try:
                with open(path) as f:
                    count = len([line.strip() for line in f if line.strip()])
                baskets[name] = count
            except Exception:
                baskets[name] = 0
        else:
            baskets[name] = 0
    return baskets
