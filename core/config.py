"""Configuration dataclass for broker settings and backtesting parameters."""

from dataclasses import dataclass


@dataclass
class BrokerConfig:
    # Base currency is informational for reports; engine uses numeric values.
    base_currency: str = "INR"
    initial_capital: float = 100_000.0  # 1 lakh
    qty_pct_of_equity: float = 0.05  # 5 percent per trade (user request)
    commission_pct: float = (
        0.11  # PER SIDE in percent (0.11% buy, 0.11% sell) = 0.22% round-trip
    )
    slippage_ticks: int = 3
    tick_size: float = 0.01  # keep 0.01 unless you have a better exchange tick table
    round_qty: bool = True
    # If True, execute fills at the next bar's open after a signal. If False, execute on the same bar's close.
    execute_on_next_open: bool = True
