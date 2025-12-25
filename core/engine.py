"""Backtesting engine for executing trading strategies on historical OHLC data."""

from typing import Any, Optional

import numpy as np
import pandas as pd

from .config import BrokerConfig
from .data_validation import DataValidation
from .strategy import Strategy


class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        strategy: Strategy,
        cfg: BrokerConfig,
        symbol: Optional[str] = None,
        cache_file: Optional[str] = None,
    ):
        req = {"open", "high", "low", "close"}
        if not req.issubset(df.columns):
            raise ValueError(f"DataFrame must include {req}")
        self.df = df.copy()
        self.strategy = strategy
        self.cfg = cfg
        self.symbol = symbol or "UNKNOWN"
        self.cache_file = cache_file

        # Validate data integrity
        validator = DataValidation(self.df, self.symbol, cache_file)
        validator.compute_fingerprint()
        validation_results = validator.validate_all()
        self.data_fingerprint = validator.fingerprint
        self.validation_results = validation_results

        if not validation_results.get("passed", False):
            import warnings

            warnings.warn(
                f"Data validation failed for {self.symbol}: {validation_results.get('errors', [])}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _fills(self, close: float) -> tuple[float, float]:
        buy = close + self.cfg.slippage_ticks * self.cfg.tick_size
        sell = close - self.cfg.slippage_ticks * self.cfg.tick_size
        return buy, sell

    def _validate_state(
        self, cash: float, qty: float, equity: float, open_trade
    ) -> None:
        """
        STATE VALIDATION: Defensive checks to catch state corruption early.

        Invariants:
        - cash >= 0 (never negative)
        - qty >= 0 (never negative)
        - equity >= 0 (never negative)
        - If qty == 0, then open_trade must be None
        - If qty > 0, then open_trade must be dict
        """
        assert cash >= 0, f"❌ INVARIANT VIOLATION: cash={cash} < 0"
        assert qty >= 0, f"❌ INVARIANT VIOLATION: qty={qty} < 0"
        assert equity >= 0, f"❌ INVARIANT VIOLATION: equity={equity} < 0"

        if qty == 0:
            assert (
                open_trade is None
            ), f"❌ INVARIANT VIOLATION: qty=0 but open_trade={open_trade} (should be None)"
        else:
            assert (
                open_trade is not None
            ), f"❌ INVARIANT VIOLATION: qty={qty} > 0 but open_trade=None (should be dict)"

    def run(self):
        self.strategy.prepare(self.df)  # side-effects only
        data = self.df  # iterate the original df
        # we'll iterate by integer position so we can reference next-row opens for fills
        idx = list(data.index)
        n = len(idx)
        comm = self.cfg.commission_pct / 100.0
        cash = self.cfg.initial_capital
        equity = cash
        qty = 0
        # open_trade now supports multiple lots for pyramiding
        open_trade = None
        entries_count = 0
        # Persistent state that survives across bars (for trailing stops, etc.)
        persistent_state = {}
        # open_trade may include optional keys: per-lot 'stop_price', and aggregate fields
        eq_rows, tr_rows, sig_rows = [], [], []
        for i, ts in enumerate(idx):
            row = data.iloc[i]
            close = float(row["close"])

            if np.isnan(close):
                eq_rows.append(
                    {
                        "time": ts,
                        "equity": equity,
                        "cash": cash,
                        "qty": qty,
                        "price": np.nan,
                    }
                )
                continue

            # Signals are determined on current bar
            # Merge persistent state with current bar state
            state = {"qty": qty, "cash": cash, "equity": equity, "symbol": self.symbol, "position": qty}
            state.update(persistent_state)  # Include persistent values (entry_price, highest_high, etc.)
            act: dict[str, Any] = self.strategy.on_bar(ts, row, state)
            # Update persistent state with any changes made by strategy
            for key in ["entry_price", "highest_high"]:
                if key in state:
                    persistent_state[key] = state[key]
            # strategy may attach an intended per-entry stop price (absolute) when signalling entry
            intended_stop = act.get("stop", None)
            signal_reason = act.get(
                "signal_reason", ""
            )  # Get signal reason from strategy
            enter = bool(act.get("enter_long", False))
            exit_ = bool(act.get("exit_long", False))

            did_exit = False
            # Exits and entries are executed at NEXT BAR's open
            # First, check per-entry stop hit (intrabar using current bar's high/low)
            stop_hit = False
            stop_reason = None

            # ===== UPDATE TRAILING STOP IF PROVIDED =====
            # Strategy can return 'updated_stop' to update stop price for existing positions (TSL)
            if qty > 0 and open_trade is not None:
                updated_stop = act.get("updated_stop", None)
                if updated_stop is not None:
                    try:
                        new_stop = float(updated_stop)
                        # Update stop price for all lots (trailing stop can only move up)
                        for lot in open_trade.get("lots", []):
                            current_stop = lot.get("stop_price")
                            if current_stop is not None:
                                current_stop = float(current_stop)
                                # TSL: only update if new stop is higher
                                if new_stop > current_stop:
                                    lot["stop_price"] = new_stop
                    except Exception:
                        pass  # Ignore errors in stop updates

            # stop detection: if any lot has a stop and low <= that stop, trigger full exit
            if qty > 0 and open_trade is not None:
                # gather stop prices from lots (if present)
                stop_prices = []
                for lot in open_trade.get("lots", []):
                    sp = lot.get("stop_price")
                    if sp is not None:
                        try:
                            stop_prices.append(float(sp))
                        except Exception:
                            pass
                if stop_prices:
                    min_sp = min(stop_prices)
                    current_low = float(row["low"])
                    if current_low <= min_sp:
                        stop_hit = True
                        stop_reason = "stop"

            if stop_hit:
                # execute stop exit at price = stop_price (simulate worst-case fill as stop_price)
                # we will treat stop fills as happening at the stop price on this bar
                # execute stop exit at price = stop_price (simulate worst-case fill as stop_price)
                sell_fill = self._fills(min_sp)[1]
                notional = sell_fill * qty
                fee = notional * (comm)
                # record each lot as its own trade row (so pyramiding counted as multiple trades)
                gross_pnl = 0.0
                comm_entry = 0.0
                for lot in open_trade.get("lots", []):
                    lp = float(lot.get("entry_price", 0.0))
                    lq = int(lot.get("entry_qty", 0))
                    l_comm = float(lot.get("commission_entry", 0.0))
                    lot_gross = (sell_fill - lp) * lq
                    exit_comm = (sell_fill * lq) * comm
                    lot_net = lot_gross - l_comm - exit_comm

                    tr_rows.append(
                        {
                            "entry_time": lot.get("entry_time"),
                            "entry_price": lp,
                            "entry_qty": lq,
                            "exit_time": ts,
                            "exit_price": sell_fill,
                            "commission_entry": l_comm,
                            "commission_exit": exit_comm,
                            "gross_pnl": lot_gross,
                            "net_pnl": lot_net,
                            "exit_reason": stop_reason,
                            "entry_signal_reason": open_trade.get(
                                "entry_signal_reason", ""
                            ),  # Store entry signal reason
                            "exit_signal_reason": "Stop Loss",  # Store signal reason for stop exits
                            # Diagnostic: record the per-lot stop price (if any) reported by strategy
                            "stop_price": lot.get("stop_price", None),
                        }
                    )
                    gross_pnl += lot_gross
                    comm_entry += l_comm
                qty = 0
                open_trade = None
                persistent_state = {}  # Clear trailing stop state
                entries_count = 0
                did_exit = True
            elif qty > 0 and exit_:
                if self.cfg.execute_on_next_open:
                    # ensure next bar exists
                    if i + 1 < n:
                        next_row = data.iloc[i + 1]
                        next_open = float(next_row["open"])
                        sell_fill = self._fills(next_open)[1]
                        notional = sell_fill * qty
                        fee = notional * (comm)
                        # compute pnl across lots
                        gross_pnl = 0.0
                        comm_entry = 0.0
                        for lot in open_trade.get("lots", []):
                            lp = lot.get("entry_price", 0.0)
                            lq = lot.get("entry_qty", 0)
                            gross_pnl += (sell_fill - lp) * lq
                            comm_entry += float(lot.get("commission_entry", 0.0))
                        gross_pnl - comm_entry - fee
                        cash += notional - fee
                        # record each lot as individual trade rows on signal exit
                        for lot in open_trade.get("lots", []):
                            lp = float(lot.get("entry_price", 0.0))
                            lq = int(lot.get("entry_qty", 0))
                            l_comm = float(lot.get("commission_entry", 0.0))
                            lot_gross = (sell_fill - lp) * lq
                            lot_net = lot_gross - l_comm - (sell_fill * lq) * comm
                            tr_rows.append(
                                {
                                    "entry_time": lot.get("entry_time"),
                                    "entry_price": lp,
                                    "entry_qty": lq,
                                    "exit_time": next_row.name,
                                    "exit_price": sell_fill,
                                    "exit_reason": "signal",
                                    "entry_signal_reason": open_trade.get(
                                        "entry_signal_reason", ""
                                    ),  # Store entry signal reason
                                    "exit_signal_reason": signal_reason,  # Store signal reason
                                    "stop_price": lot.get("stop_price", None),
                                    "commission_entry": l_comm,
                                    "commission_exit": (sell_fill * lq) * comm,
                                    "gross_pnl": lot_gross,
                                    "net_pnl": lot_net,
                                }
                            )
                        qty = 0
                        open_trade = None
                        persistent_state = {}  # Clear trailing stop state
                        entries_count = 0
                        did_exit = True
                    else:
                        # can't execute exit (no next open) — skip
                        pass
                else:
                    # execute on same-bar close
                    sell_fill = self._fills(close)[1]
                    notional = sell_fill * qty
                    fee = notional * (comm)
                    # compute pnl across lots
                    gross_pnl = 0.0
                    comm_entry = 0.0
                    for lot in open_trade.get("lots", []):
                        lp = lot.get("entry_price", 0.0)
                        lq = lot.get("entry_qty", 0)
                        gross_pnl += (sell_fill - lp) * lq
                        comm_entry += float(lot.get("commission_entry", 0.0))
                    gross_pnl - comm_entry - fee
                    cash += notional - fee
                    # record each lot as its own trade on same-bar close
                    for lot in open_trade.get("lots", []):
                        lp = float(lot.get("entry_price", 0.0))
                        lq = int(lot.get("entry_qty", 0))
                        l_comm = float(lot.get("commission_entry", 0.0))
                        lot_gross = (sell_fill - lp) * lq
                        lot_net = lot_gross - l_comm - (sell_fill * lq) * comm
                        tr_rows.append(
                            {
                                "entry_time": lot.get("entry_time"),
                                "entry_price": lp,
                                "entry_qty": lq,
                                "exit_time": ts,
                                "exit_price": sell_fill,
                                "exit_reason": "signal",
                                "entry_signal_reason": open_trade.get(
                                    "entry_signal_reason", ""
                                ),  # Store entry signal reason
                                "exit_signal_reason": signal_reason,  # Store signal reason
                                "stop_price": lot.get("stop_price", None),
                                "commission_entry": l_comm,
                                "commission_exit": (sell_fill * lq) * comm,
                                "gross_pnl": lot_gross,
                                "net_pnl": lot_net,
                            }
                        )
                    qty = 0
                    open_trade = None
                    persistent_state = {}  # Clear trailing stop state
                    did_exit = True

            did_entry = False
            # allow pyramiding: only add entry if current entries_count < strategy.pyramiding
            pyramiding = int(getattr(self.strategy, "pyramiding", 1))
            if entries_count < pyramiding and enter:
                if self.cfg.execute_on_next_open:
                    # ensure next bar exists for entry fill
                    if i + 1 < n:
                        next_row = data.iloc[i + 1]
                        next_open = float(next_row["open"])
                        buy_fill = self._fills(next_open)[0]
                        # size using initial capital so each trade uses fixed percentage of initial capital
                        shares = self.strategy.size(
                            equity=self.cfg.initial_capital,
                            price=buy_fill,
                            cfg=self.cfg,
                        )
                        if shares > 0:
                            notional = buy_fill * shares
                            fee = notional * (comm)
                            total = notional + fee
                            if total <= cash:
                                cash -= total
                                # add this lot to open_trade (create if needed)
                                if open_trade is None:
                                    open_trade = {
                                        "lots": [],
                                        "first_entry_time": next_row.name,
                                        "entry_signal_reason": signal_reason,  # Store entry signal reason
                                    }
                                # capture per-entry stop if provided by strategy (absolute price)
                                stop_price = None
                                if intended_stop is not None:
                                    try:
                                        stop_price = float(intended_stop)
                                    except Exception:
                                        stop_price = None

                                lot = {
                                    "entry_time": next_row.name,
                                    "entry_price": buy_fill,
                                    "entry_qty": shares,
                                    "commission_entry": fee,
                                    "stop_price": stop_price,
                                }
                                # allow strategy to augment the lot (compute ATR-based stops etc.)
                                try:
                                    meta = self.strategy.on_entry(
                                        lot["entry_time"], lot["entry_price"], state
                                    )
                                    # Sync state changes from on_entry to persistent_state
                                    for key in ["entry_price", "highest_high"]:
                                        if key in state:
                                            persistent_state[key] = state[key]
                                    if (
                                        isinstance(meta, dict)
                                        and meta.get("stop") is not None
                                    ):
                                        try:
                                            lot["stop_price"] = float(meta.get("stop"))
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                open_trade["lots"].append(lot)
                                # recompute aggregate qty and avg entry price/commissions
                                qty = sum(
                                    int(lot.get("entry_qty", 0))
                                    for lot in open_trade["lots"]
                                )
                                total_cost = sum(
                                    float(lot.get("entry_price", 0.0))
                                    * int(lot.get("entry_qty", 0))
                                    for lot in open_trade["lots"]
                                )
                                total_comm = sum(
                                    float(lot.get("commission_entry", 0.0))
                                    for lot in open_trade["lots"]
                                )
                                open_trade["avg_entry_price"] = (
                                    (total_cost / qty) if qty else None
                                )
                                open_trade["commission_entry"] = total_comm
                                entries_count += 1
                                did_entry = True
                    else:
                        # can't enter (no next open)
                        pass
                else:
                    # execute entry on same-bar close
                    buy_fill = self._fills(close)[0]
                    # size using initial capital so each trade uses fixed percentage of initial capital
                    shares = self.strategy.size(
                        equity=self.cfg.initial_capital, price=buy_fill, cfg=self.cfg
                    )
                    if shares > 0:
                        notional = buy_fill * shares
                        fee = notional * (comm)
                        total = notional + fee
                        if total <= cash:
                            cash -= total
                            qty = shares
                            open_trade = {
                                "entry_time": ts,
                                "entry_price": buy_fill,
                                "entry_qty": shares,
                                "commission_entry": fee,
                            }
                            did_entry = True

            equity = cash + qty * close

            # STATE VALIDATION: Check invariants (optional defensive check)
            # Uncomment to enable runtime state validation during backtest
            # self._validate_state(cash, qty, equity, open_trade)

            eq_rows.append(
                {"time": ts, "equity": equity, "cash": cash, "qty": qty, "price": close}
            )
            sig_rows.append(
                {
                    "time": ts,
                    "enter_long": enter,
                    "exit_long": exit_,
                    "did_entry": did_entry,
                    "did_exit": did_exit,
                }
            )
            # increment time_in_trade for open position bookkeeping (useful for time stops)
            if qty > 0 and open_trade is not None:
                try:
                    open_trade["time_in_trade"] = (
                        int(open_trade.get("time_in_trade", 0)) + 1
                    )
                except Exception:
                    open_trade["time_in_trade"] = 0

        # CORRECT HANDLING: Export open trades WITHOUT forcing them to close
        # Open trades should remain open in real trading - not artificially closed at backtest end
        if qty > 0 and open_trade is not None:
            # Export open trade with exit_time = NaN to indicate it's still open

            if hasattr(open_trade, "get") and "lots" in open_trade:
                # Handle pyramiding case (multiple lots)
                for lot in open_trade["lots"]:
                    entry_qty = int(lot.get("entry_qty", 0))
                    entry_price = float(lot.get("entry_price", 0))
                    if entry_qty > 0 and entry_price > 0:
                        # Export as open trade - no artificial exit
                        tr_rows.append(
                            {
                                "entry_time": lot.get("entry_time"),
                                "exit_time": None,  # Open trade - no exit
                                "entry_price": entry_price,
                                "exit_price": None,  # Open trade - no exit price
                                "entry_qty": entry_qty,
                                "exit_qty": None,  # Open trade - no exit
                                "commission_entry": lot.get("commission_entry", 0),
                                "commission_exit": 0,  # No exit commission for open trade
                                "gross_pnl": None,  # Open trade - unrealized P&L tracked in equity curve
                                "net_pnl": None,  # Open trade - unrealized P&L tracked in equity curve
                                "trade_status": "OPEN",  # Mark as open trade
                                "stop_price": lot.get("stop_price", None),
                            }
                        )
            else:
                # Handle simple case (single position)
                entry_price = float(open_trade.get("entry_price", 0))
                entry_qty = int(open_trade.get("entry_qty", 0))
                if entry_qty > 0 and entry_price > 0:
                    # Export as open trade - no artificial exit
                    tr_rows.append(
                        {
                            "entry_time": open_trade.get("entry_time"),
                            "exit_time": None,  # Open trade - no exit
                            "entry_price": entry_price,
                            "exit_price": None,  # Open trade - no exit price
                            "entry_qty": entry_qty,
                            "exit_qty": None,  # Open trade - no exit
                            "commission_entry": open_trade.get("commission_entry", 0),
                            "commission_exit": 0,  # No exit commission for open trade
                            "gross_pnl": None,  # Open trade - unrealized P&L tracked in equity curve
                            "net_pnl": None,  # Open trade - unrealized P&L tracked in equity curve
                            "trade_status": "OPEN",  # Mark as open trade
                        }
                    )

        equity_df = pd.DataFrame(eq_rows).set_index("time")
        trades_df = pd.DataFrame(tr_rows)
        signals_df = pd.DataFrame(sig_rows).set_index("time")

        return trades_df, equity_df, signals_df
