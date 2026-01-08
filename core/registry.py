"""Strategy registry for dynamically instantiating strategies by name."""

# core/registry.py
import json

from strategies.bollinger_rsi import BollingerRSIStrategy
from strategies.candlestick_patterns import CandlestickPatternsStrategy
from strategies.dual_tema_lsma import DualTemaLsmaStrategy
from strategies.ema_crossover import EMAcrossoverStrategy
from strategies.ichimoku_cloud import IchimokuCloud
from strategies.ichimoku_simple import IchimokuSimple
from strategies.kama_crossover_filtered import KAMACrossoverFiltered
from strategies.knoxville import KnoxvilleStrategy
from strategies.stoch_rsi_pyramid_long import StochRSIPyramidLongStrategy
from strategies.supertrend_dema import SupertrendDEMAStrategy
from strategies.supertrend_vix_atr import SupertrendVixAtrStrategy
from strategies.tema_lsma_crossover import TemaLsmaCrossover
from strategies.triple_ema_aligned import TripleEMAAlignedStrategy
from strategies.weekly_rotation import (
    WeeklyRotationStrategy,
    WeeklyMomentumStrategy,
    WeeklyMeanReversionStrategy,
)
from strategies.weekly_green_bb import WeeklyGreenBBStrategy

_REG = {
    "bollinger_rsi": BollingerRSIStrategy,
    "candlestick_patterns": CandlestickPatternsStrategy,
    "dual_tema_lsma": DualTemaLsmaStrategy,
    "ema_crossover": EMAcrossoverStrategy,
    "ichimoku_cloud": IchimokuCloud,
    "ichimoku_simple": IchimokuSimple,
    "kama_crossover_filtered": KAMACrossoverFiltered,
    "knoxville": KnoxvilleStrategy,
    "stoch_rsi_pyramid_long": StochRSIPyramidLongStrategy,
    "supertrend_dema": SupertrendDEMAStrategy,
    "supertrend_vix_atr": SupertrendVixAtrStrategy,
    "tema_lsma_crossover": TemaLsmaCrossover,
    "triple_ema_aligned": TripleEMAAlignedStrategy,
    "weekly_rotation": WeeklyRotationStrategy,
    "weekly_momentum": WeeklyMomentumStrategy,
    "weekly_mean_reversion": WeeklyMeanReversionStrategy,
    "weekly_green_bb": WeeklyGreenBBStrategy,
}


def make_strategy(name: str, params_json: str = "{}"):
    if name not in _REG:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(_REG.keys())}")
    kwargs = json.loads(params_json) if params_json else {}
    return _REG[name](**kwargs)
