"""Configuration dataclass for broker settings and backtesting parameters."""

from dataclasses import dataclass


@dataclass
class BrokerConfig:
    # Base currency is informational for reports; engine uses numeric values.
    base_currency: str = "INR"
    initial_capital: float = 100_000.0  # 1 lakh
    qty_pct_of_equity: float = 0.05  # 5 percent per trade (user request)
    commission_pct: float = (
        0.18  # PER SIDE in percent (0.18% buy, 0.18% sell) = 0.36% round-trip
    )
    slippage_ticks: int = 0  # No slippage for daily data (execute at exact open price)
    tick_size: float = 0.01  # keep 0.01 unless you have a better exchange tick table
    round_qty: bool = True
    # If True, execute fills at the next bar's open after a signal. If False, execute on the same bar's close.
    execute_on_next_open: bool = True
    # Position sizing mode:
    # - False (default): Fixed % of INITIAL capital (strategy evaluation - all trades same size)
    # - True: Fixed % of CURRENT equity (portfolio evaluation - wins compound)
    compounding: bool = False
