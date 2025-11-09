"""Strategy registry for dynamically instantiating strategies by name."""

# core/registry.py
import json

from strategies.bollinger_rsi import BollingerRSIStrategy
from strategies.ema_crossover import EMAcrossoverStrategy
from strategies.ichimoku import IchimokuQuantLabWrapper
from strategies.knoxville import KnoxvilleStrategy

_REG = {
    "bollinger_rsi": BollingerRSIStrategy,
    "ema_crossover": EMAcrossoverStrategy,
    "ichimoku": IchimokuQuantLabWrapper,
    "knoxville": KnoxvilleStrategy,
}


def make_strategy(name: str, params_json: str = "{}"):
    if name not in _REG:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(_REG.keys())}")
    kwargs = json.loads(params_json) if params_json else {}
    return _REG[name](**kwargs)
