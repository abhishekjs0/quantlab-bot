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

# Basket configuration
DEFAULT_BASKET_SIZE = "test"

BASKET_FILES = {
    "test": DATA_DIR / "basket_test.txt",
    "small": DATA_DIR / "basket_small.txt",
    "mid": DATA_DIR / "basket_mid.txt",
    "large": DATA_DIR / "basket_large.txt",
    "mega": DATA_DIR / "basket_mega.txt",
    "default": DATA_DIR / "basket_default.txt",
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
