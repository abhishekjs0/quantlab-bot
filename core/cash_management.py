"""T+1 Cash Management system for tracking settlement and available capital.

Handles:
- Settlement date tracking (T+1 for India NSE)
- Blocked vs available cash
- Cash pool management across trades
- Position tracking with settlement information
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class SettlementRecord:
    """Records when cash becomes available from a sale."""

    exit_time: pd.Timestamp
    settlement_date: pd.Timestamp  # T+1 from exit
    amount: float  # gross proceeds (before commission)
    commission: float  # commission paid on exit
    net_amount: float  # amount available after commission


@dataclass
class T1CashManager:
    """Manages T+1 settlement rules for Indian equity trading.

    In India NSE (T+1 settlement):
    - Sell today → money available tomorrow (next trading day)
    - Before settlement, cash is blocked and cannot be reused
    - After settlement, cash is added to available pool

    Attributes:
        initial_capital: Starting cash
        settlement_delay: Number of trading days until settlement (1 for T+1)
    """

    initial_capital: float
    settlement_delay: int = 1  # T+1 for India
    available_cash: float = field(init=False)
    blocked_cash: float = field(init=False)
    settlement_queue: list[SettlementRecord] = field(default_factory=list)
    total_capital: float = field(init=False)

    def __post_init__(self):
        """Initialize cash pools."""
        self.available_cash = self.initial_capital
        self.blocked_cash = 0.0
        self.total_capital = self.initial_capital

    def get_available_cash(self) -> float:
        """Get cash available for new trades (after blocking for unsettled sales)."""
        return self.available_cash

    def get_total_capital(self) -> float:
        """Get total capital (available + blocked)."""
        return self.available_cash + self.blocked_cash

    def get_blocked_cash(self) -> float:
        """Get cash blocked until settlement."""
        return self.blocked_cash

    def record_entry(self, entry_price: float, qty: int, commission: float):
        """Record cash outflow on trade entry.

        Args:
            entry_price: Entry price per share
            qty: Quantity bought
            commission: Commission paid on entry
        """
        cost = entry_price * qty + commission
        if cost > self.available_cash:
            raise ValueError(
                f"Insufficient cash: {cost:.2f} > {self.available_cash:.2f}"
            )
        self.available_cash -= cost
        self.total_capital -= commission  # Commission reduces total capital

    def record_exit(
        self, exit_time: pd.Timestamp, exit_price: float, qty: int, commission: float
    ) -> float:
        """Record cash inflow on trade exit (creates settlement record).

        Args:
            exit_time: Time of exit (trade execution)
            exit_price: Exit price per share
            qty: Quantity sold
            commission: Commission paid on exit

        Returns:
            Net amount (proceeds after commission)
        """
        gross_proceeds = exit_price * qty
        net_amount = gross_proceeds - commission

        # Calculate settlement date (T+1)
        # In practice, this would be the next trading day
        # For backtesting, we assume each day is a trading day
        # In real trading, you'd need a trading calendar
        settlement_date = exit_time + pd.Timedelta(days=self.settlement_delay)

        # Create settlement record
        settlement = SettlementRecord(
            exit_time=exit_time,
            settlement_date=settlement_date,
            amount=gross_proceeds,
            commission=commission,
            net_amount=net_amount,
        )
        self.settlement_queue.append(settlement)

        # Block cash until settlement
        self.blocked_cash += net_amount

        return net_amount

    def process_settlements(self, current_time: pd.Timestamp) -> float:
        """Process any settlements that have occurred by current_time.

        Args:
            current_time: Current timestamp for settlement checks

        Returns:
            Amount settled and added to available cash
        """
        settled_amount = 0.0
        unsettled = []

        for settlement in self.settlement_queue:
            if settlement.settlement_date <= current_time:
                # This settlement has completed
                settled_amount += settlement.net_amount
                self.available_cash += settlement.net_amount
                self.blocked_cash -= settlement.net_amount
            else:
                # Not yet settled
                unsettled.append(settlement)

        # Keep only unsettled records
        self.settlement_queue = unsettled

        return settled_amount

    def get_settlement_status(self) -> dict:
        """Get detailed settlement information.

        Returns:
            Dict with available cash, blocked cash, and pending settlements
        """
        return {
            "available_cash": self.available_cash,
            "blocked_cash": self.blocked_cash,
            "total_capital": self.get_total_capital(),
            "pending_settlements": len(self.settlement_queue),
            "settlement_queue": [
                {
                    "exit_time": str(s.exit_time),
                    "settlement_date": str(s.settlement_date),
                    "amount": s.amount,
                    "commission": s.commission,
                    "net_amount": s.net_amount,
                }
                for s in self.settlement_queue
            ],
        }

    def reset(self):
        """Reset to initial state."""
        self.available_cash = self.initial_capital
        self.blocked_cash = 0.0
        self.total_capital = self.initial_capital
        self.settlement_queue = []
