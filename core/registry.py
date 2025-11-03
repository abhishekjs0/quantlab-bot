"""Strategy registry for dynamically instantiating strategies by name."""

# core/registry.py
import json

from strategies.envelope_kd import EnvelopeKDStrategy
from strategies.ichimoku import IchimokuQuantLabWrapper

_REG = {
    "ichimoku": IchimokuQuantLabWrapper,
    "envelope_kd": EnvelopeKDStrategy,
}


def make_strategy(name: str, params_json: str = "{}"):
    if name not in _REG:
        raise ValueError(f"Unknown strategy '{name}'. Available: {list(_REG.keys())}")
    kwargs = json.loads(params_json) if params_json else {}
    return _REG[name](**kwargs)
