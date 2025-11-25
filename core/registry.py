"""Strategy registry for dynamically instantiating strategies by name."""

# core/registry.py
import json

from strategies.bollinger_rsi import BollingerRSIStrategy
from strategies.candlestick_patterns import CandlestickPatternsStrategy
from strategies.dual_tema_lsma import DualTemaLsmaStrategy
from strategies.ema_crossover import EMAcrossoverStrategy
from strategies.ema_crossover_21_55 import EMA1355Strategy
from strategies.ichimoku import IchimokuQuantLabWrapper
from strategies.ichimoku_tenkan_kijun import IchimokuTenkanKijunStrategy
from strategies.kama_crossover import KAMACrossover
from strategies.kama_crossover_filtered import KAMACrossoverFiltered
from strategies.knoxville import KnoxvilleStrategy
from strategies.triple_ema_aligned import TripleEMAAlignedStrategy

_REG = {
    "bollinger_rsi": BollingerRSIStrategy,
    "candlestick_patterns": CandlestickPatternsStrategy,
    "dual_tema_lsma": DualTemaLsmaStrategy,
    "ema_crossover": EMAcrossoverStrategy,
    "ema_crossover_21_55": EMA1355Strategy,
    "ichimoku": IchimokuQuantLabWrapper,
    "ichimoku_tenkan_kijun": IchimokuTenkanKijunStrategy,
    "kama_crossover": KAMACrossover,
    "kama_crossover_filtered": KAMACrossoverFiltered,
    "knoxville": KnoxvilleStrategy,
    "triple_ema_aligned": TripleEMAAlignedStrategy,
}


def make_strategy(name: str, params_json: str = "{}"):
    if name not in _REG:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(_REG.keys())}")
    kwargs = json.loads(params_json) if params_json else {}
    return _REG[name](**kwargs)
