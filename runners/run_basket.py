# runners/run_basket.py
import argparse
import logging
import os
import signal
import sys
import time
import traceback
from contextlib import contextmanager
from typing import Optional

import pandas as pd

from core.benchmark import BenchmarkError, calculate_alpha_beta
from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.monitoring import BacktestMonitor, optimize_window_processing
from core.perf import (
    compute_portfolio_trade_metrics,
    compute_trade_metrics_table,
)
from core.registry import make_strategy
from core.report import make_run_dir, save_summary
from data.loaders import load_many_india

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BARS_PER_YEAR_MAP: dict[str, int] = {"1d": 245, "60m": 1470}

# Timeout configuration
DEFAULT_TIMEOUT = 300  # 5 minutes per operation
SYMBOL_TIMEOUT = 60  # 1 minute per symbol
TOTAL_TIMEOUT = 3600  # 1 hour total limit


class TimeoutError(Exception):
    """Custom timeout exception."""

    pass


@contextmanager
def timeout_handler(seconds: int, error_message: str = "Operation timed out"):
    """Context manager for operation timeouts."""

    def signal_handler(signum, frame):
        raise TimeoutError(error_message)

    # Set the signal handler and alarm
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Clean up
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def safe_operation(
    func,
    *args,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    operation_name: str = "operation",
    **kwargs,
):
    """Safely execute an operation with timeout and error handling."""
    try:
        logger.info(f"Starting {operation_name}...")
        with timeout_handler(
            timeout_seconds, f"{operation_name} timed out after {timeout_seconds}s"
        ):
            result = func(*args, **kwargs)
        logger.info(f"Completed {operation_name} successfully")
        return result
    except TimeoutError as e:
        logger.error(f"Timeout in {operation_name}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in {operation_name}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise


def retry_operation(
    func,
    *args,
    max_retries: int = 3,
    delay: float = 1.0,
    operation_name: str = "operation",
    **kwargs,
):
    """Retry an operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = delay * (2**attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed for {operation_name}: {e}"
                )
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(
                    f"All {max_retries} attempts failed for {operation_name}: {e}"
                )
                raise


def _read_symbols_from_txt(txt_path: str) -> list[str]:
    with open(txt_path) as f:
        lines = [ln.strip() for ln in f.read().splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("Empty symbols file")
    if lines[0].lower() == "symbol":
        lines = lines[1:]
    return lines


def _slice_df_years(df: pd.DataFrame, years: int | None) -> pd.DataFrame:
    if years is None:
        return df
    last = df.index.max()
    first = last - pd.DateOffset(years=years)
    return df.loc[df.index >= first]


def _sanitize_symbol(sym: str) -> str:
    return "".join([c if (c.isalnum() or c in ("_", "-")) else "_" for c in sym])


def _format_and_enforce_totals(
    out_df: pd.DataFrame, total_net_pct: float
) -> pd.DataFrame:
    """Format percent/numeric columns for human CSV and enforce TOTAL Net P&L parity.

    - total_net_pct: numeric percent (e.g. 12.3456 -> 12.3456)
    Returns a new DataFrame with formatted strings for percent fields and integer fields.
    """
    df = out_df.copy()
    # Normalize column names that tests may expect
    # Accept either 'Max equity drawdown' or 'Max equity drawdown %'
    dd_col = None
    if "Max equity drawdown %" in df.columns:
        dd_col = "Max equity drawdown %"
    elif "Max equity drawdown" in df.columns:
        dd_col = "Max equity drawdown"

    # Enforce TOTAL Net P&L
    if "Net P&L %" in df.columns:
        # ensure numeric
        try:
            df["Net P&L % (num)"] = pd.to_numeric(df["Net P&L %"], errors="coerce")
        except Exception:
            df["Net P&L % (num)"] = 0.0
        # Set TOTAL
        total_mask = df["Symbol"] == "TOTAL"
        if total_mask.any():
            df.loc[total_mask, "Net P&L % (num)"] = float(total_net_pct)

        # Format percent columns
        def fmt_pct(v):
            try:
                return f"{float(v):.2f}%"
            except Exception:
                return "0.00%"

        df["Net P&L %"] = df["Net P&L % (num)"].apply(fmt_pct)

    # Format drawdown as percent
    if dd_col is not None:
        try:
            df["_dd_num"] = pd.to_numeric(df[dd_col], errors="coerce")
            # if drawdown appears fractional (< 2) assume decimal and convert to percent
            if not df["_dd_num"].dropna().empty and df["_dd_num"].abs().max() <= 2.0:
                df["_dd_num"] = df["_dd_num"].astype(float)
            df[dd_col] = df["_dd_num"].apply(
                lambda v: (f"{float(v):.2f}%" if pd.notna(v) else "0.00%")
            )
            df = df.drop(columns=["_dd_num"], errors="ignore")
        except Exception:
            pass

    # Format integer-like columns
    if "Total trades" in df.columns:
        df["Total trades"] = df["Total trades"].apply(
            lambda v: str(int(v)) if (pd.notna(v) and not str(v).strip() == "") else "0"
        )

    return df


def _export_trades_events(
    trades_df: pd.DataFrame,
    df: pd.DataFrame,
    run_dir: str,
    sym: str,
    label: str,
    initial_capital: float = 100000.0,
) -> str:
    """Export TradingView-style trades CSV for a symbol and return path (or empty string).

    This function writes only TradingView-format CSVs (no duplicate event-style CSVs).
    """
    if trades_df.empty:
        return ""

    sym_safe = _sanitize_symbol(sym)
    tv_rows = []

    for i, tr in trades_df.reset_index(drop=True).iterrows():
        trade_no = i + 1
        entry_time = tr["entry_time"]
        exit_time = tr["exit_time"]
        entry_price = (
            float(tr["entry_price"]) if not pd.isna(tr["entry_price"]) else None
        )
        exit_price = (
            float(tr.get("exit_price", None))
            if not pd.isna(tr.get("exit_price", None))
            else None
        )
        qty = int(tr.get("entry_qty", 0))

        # compute run-up/drawdown (price * qty P&L) over the trade
        run_up = None
        drawdown = None
        try:
            price_series = df.loc[entry_time:exit_time]["close"].astype(float)
            pnl_series = (price_series - entry_price) * qty
            if not pnl_series.empty:
                run_up = float(pnl_series.max())
                drawdown = float(pnl_series.min())
        except Exception:
            run_up = None
            drawdown = None

        net_pnl = (
            float(tr.get("net_pnl", 0.0))
            if not pd.isna(tr.get("net_pnl", 0.0))
            else 0.0
        )
        pos_value_exit = (
            (exit_price * qty) if (exit_price is not None and qty) else None
        )
        pos_value_entry = (
            (entry_price * qty) if (entry_price is not None and qty) else None
        )  # FIXED: Add entry value
        net_pnl_exit = net_pnl
        run_up_exit = run_up
        drawdown_exit = drawdown

        # Exit row (TradingView ordering: exit then entry)
        # FIXED: Use entry value as denominator for percentage calculations (trade size basis)
        tv_pos_value = pos_value_exit  # For display
        tv_pos_value_base = pos_value_entry  # For percentage calculations
        tv_net_pct = None
        tv_run_pct = None
        tv_dd_pct = None
        if tv_pos_value_base and tv_pos_value_base != 0:
            tv_net_pct = (
                round((net_pnl_exit / tv_pos_value_base) * 100, 2)
                if net_pnl_exit is not None
                else None
            )
            tv_run_pct = (
                round((run_up_exit / tv_pos_value_base) * 100, 2)
                if run_up_exit is not None
                else None
            )
            tv_dd_pct = (
                round((drawdown_exit / tv_pos_value_base) * 100, 2)
                if drawdown_exit is not None
                else None
            )

        tv_rows.append(
            {
                "Trade #": trade_no,
                "Type": "Exit long",
                "Date/Time": exit_time,
                "Signal": "Close entry(s) order LONG",
                "Price INR": exit_price,
                "Position size (qty)": qty,
                "Position size (value)": (
                    round(tv_pos_value, 2) if tv_pos_value is not None else None
                ),
                "Net P&L INR": (
                    round(net_pnl_exit, 2) if net_pnl_exit is not None else None
                ),
                "Net P&L %": tv_net_pct,
                "Run-up INR": (
                    round(run_up_exit, 2) if run_up_exit is not None else None
                ),
                "Run-up %": tv_run_pct,
                "Drawdown INR": (
                    round(drawdown_exit, 2) if drawdown_exit is not None else None
                ),
                "Drawdown %": tv_dd_pct,
                "Cumulative P&L INR": None,  # computed later if needed
                "Cumulative P&L %": None,
            }
        )

        # Entry row
        tv_pos_value_entry = (
            (entry_price * qty) if (entry_price is not None and qty) else None
        )
        tv_rows.append(
            {
                "Trade #": trade_no,
                "Type": "Entry long",
                "Date/Time": entry_time,
                "Signal": "LONG",
                "Price INR": entry_price,
                "Position size (qty)": qty,
                "Position size (value)": (
                    round(tv_pos_value_entry, 2)
                    if tv_pos_value_entry is not None
                    else None
                ),
                "Net P&L INR": "",
                "Net P&L %": "",
                "Run-up INR": "",
                "Run-up %": "",
                "Drawdown INR": "",
                "Drawdown %": "",
                "Cumulative P&L INR": None,
                "Cumulative P&L %": None,
            }
        )

    # write TradingView-format CSV
    try:
        if tv_rows:
            tv_df = pd.DataFrame(tv_rows)
            if "Date/Time" in tv_df.columns:
                tv_df["Date/Time"] = tv_df["Date/Time"].apply(
                    lambda t: t.strftime("%Y-%m-%d") if hasattr(t, "strftime") else t
                )
            tv_csv_path = os.path.join(run_dir, f"trades_TV_{label}_{sym_safe}.csv")
            tv_df.to_csv(tv_csv_path, index=False)
            return tv_csv_path
    except Exception:
        return ""

    return ""


def _generate_strategy_summary(
    run_dir: str,
    portfolio_curves: dict[str, pd.DataFrame],
    trades_by_window: dict[str, pd.DataFrame],
    portfolio_metrics: dict[str, pd.DataFrame],
    initial_capital: float = 100000.0,
) -> str:
    """Generate comprehensive strategy backtests summary file.

    Args:
        run_dir: Output directory
        portfolio_curves: Dict mapping label (e.g. "1Y") to daily portfolio curve DataFrame
        trades_by_window: Dict mapping label to consolidated trades DataFrame
        portfolio_metrics: Dict mapping label to portfolio_key_metrics DataFrame (for TOTAL row data)
        initial_capital: Starting capital

    Returns:
        Path to generated strategy_backtests_summary.csv file
    """
    import numpy as np

    summary_rows = []

    for label, port_df in portfolio_curves.items():
        if port_df.empty:
            continue

        try:
            # Time metrics
            start_date = port_df.index[0]
            end_date = port_df.index[-1]
            duration = end_date - start_date
            duration_str = str(duration)

            # Equity metrics (handle both "Equity" and "equity" column names)
            equity_col = "Equity" if "Equity" in port_df.columns else "equity"
            equity_start = float(port_df[equity_col].iloc[0])
            equity_end = float(port_df[equity_col].iloc[-1])
            float(port_df[equity_col].max())  # Return metrics
            total_return_pct = (
                ((equity_end / equity_start) - 1.0) * 100.0 if equity_start > 0 else 0.0
            )

            # Annualization
            n_days = max((end_date - start_date).days, 1)
            n_years = n_days / 365.25
            cagr_pct = (
                ((equity_end / equity_start) ** (1.0 / n_years) - 1.0) * 100.0
                if equity_start > 0 and n_years > 0
                else 0.0
            )

            # Exposure statistics
            exposure_col = (
                "Avg exposure" if "Avg exposure" in port_df.columns else "avg_exposure"
            )
            avg_exposure_value = float(port_df[exposure_col].mean())
            avg_exposure_pct = (
                (avg_exposure_value / initial_capital * 100.0)
                if initial_capital > 0
                else 0.0
            )

            # Get Max Drawdown and IRR from portfolio_metrics (TOTAL row) if available
            metrics_df = portfolio_metrics.get(label)
            if metrics_df is not None and not metrics_df.empty:
                total_metrics = metrics_df[metrics_df["Symbol"] == "TOTAL"]
                if not total_metrics.empty:
                    max_dd_pct = float(total_metrics["Max equity drawdown %"].iloc[0])
                    irr_pct = float(total_metrics["IRR %"].iloc[0])
                else:
                    max_dd_pct = 0.0
                    irr_pct = 0.0
            else:
                max_dd_pct = 0.0
                irr_pct = 0.0

            # Equity metrics

            dd_pct_col = (
                "Drawdown %" if "Drawdown %" in port_df.columns else "drawdown_pct"
            )

            # Drawdown duration: consecutive days with exposure
            drawdown_durations = []
            in_dd = False
            dd_start = None
            for i, val in enumerate(port_df[dd_pct_col].fillna(0.0)):
                if val > 0:  # in drawdown
                    if not in_dd:
                        in_dd = True
                        dd_start = i
                else:
                    if in_dd:
                        drawdown_durations.append(i - dd_start)
                        in_dd = False
            if in_dd and dd_start is not None:
                drawdown_durations.append(len(port_df) - dd_start)

            max_dd_duration = max(drawdown_durations) if drawdown_durations else 0

            # Volatility (annualized) - calculate from Equity column, not Total Return %
            equity_col_for_returns = (
                "Equity" if "Equity" in port_df.columns else "equity"
            )
            daily_equity_returns = port_df[equity_col_for_returns].pct_change().dropna()
            if len(daily_equity_returns) > 0:
                daily_vol = float(daily_equity_returns.std())
                annual_vol = daily_vol * np.sqrt(245)  # 245 trading days per year
            else:
                annual_vol = 0.0

            # Trade statistics
            trades_df = trades_by_window.get(label)
            if trades_df is not None and not trades_df.empty:
                exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                if len(exit_trades) > 0:
                    num_trades = len(exit_trades)

                    # Extract P&L values (strip '%' suffix if present)
                    pnl_str = (
                        exit_trades["Net P&L %"]
                        .astype(str)
                        .str.replace("%", "")
                        .str.strip()
                    )
                    pnl_values = pd.to_numeric(pnl_str, errors="coerce").dropna()
                    if len(pnl_values) > 0:
                        winning_trades = (pnl_values > 0).sum()
                        win_rate = (
                            (winning_trades / num_trades * 100.0)
                            if num_trades > 0
                            else 0.0
                        )
                        avg_trade_pct = float(pnl_values.mean())
                        best_trade_pct = float(pnl_values.max())
                        worst_trade_pct = float(pnl_values.min())

                        # Profit factor
                        wins = pnl_values[pnl_values > 0].sum()
                        losses = abs(pnl_values[pnl_values < 0].sum())
                        profit_factor = (
                            float(wins / losses)
                            if losses > 0
                            else (float("inf") if wins > 0 else 0.0)
                        )

                        # Expectancy (avg weighted by probability)
                        # Use average win/loss instead of best/worst trades for realistic calculation
                        win_avg = (
                            pnl_values[pnl_values > 0].mean()
                            if (pnl_values > 0).any()
                            else 0.0
                        )
                        loss_avg = (
                            pnl_values[pnl_values < 0].mean()
                            if (pnl_values < 0).any()
                            else 0.0
                        )
                        expectancy = (win_rate / 100.0 * win_avg) + (
                            (1 - win_rate / 100.0) * loss_avg
                        )
                    else:
                        num_trades = 0
                        win_rate = 0.0
                        avg_trade_pct = 0.0
                        best_trade_pct = 0.0
                        worst_trade_pct = 0.0
                        profit_factor = 0.0
                        expectancy = 0.0

                    # Trade duration
                    entry_trades = trades_df[trades_df["Type"] == "Entry long"].copy()
                    exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()

                    if len(entry_trades) > 0 and len(exit_trades) > 0:
                        # Filter out trades with empty/NaN dates
                        exit_trades = exit_trades[exit_trades["Date/Time"].notna()]
                        exit_trades = exit_trades[exit_trades["Date/Time"] != ""]

                        if len(exit_trades) > 0:
                            entry_trades["Date/Time"] = pd.to_datetime(
                                entry_trades["Date/Time"]
                            )
                            exit_trades_sorted = exit_trades.copy()
                            exit_trades_sorted["Date/Time"] = pd.to_datetime(
                                exit_trades_sorted["Date/Time"]
                            )

                            # Match entries with exits
                            trade_durations = []
                            for _, entry_row in entry_trades.iterrows():
                                trade_num = entry_row.get("Trade #")
                                # Find matching exit
                                matching_exits = exit_trades_sorted[
                                    exit_trades_sorted["Trade #"] == trade_num
                                ]
                                if not matching_exits.empty:
                                    exit_row = matching_exits.iloc[0]
                                    duration_days = (
                                        pd.to_datetime(exit_row["Date/Time"])
                                        - pd.to_datetime(entry_row["Date/Time"])
                                    ).days
                                    if duration_days >= 0:  # Only count valid durations
                                        trade_durations.append(duration_days)

                            max_trade_duration = (
                                max(trade_durations) if trade_durations else 0
                            )
                            if trade_durations:
                                avg_duration_days = np.mean(trade_durations)
                                avg_trade_duration = (
                                    int(avg_duration_days)
                                    if not np.isnan(avg_duration_days)
                                    else 0
                                )
                            else:
                                avg_trade_duration = 0
                        else:
                            max_trade_duration = 0
                            avg_trade_duration = 0
                    else:
                        max_trade_duration = 0
                        avg_trade_duration = 0
                else:
                    num_trades = 0
                    win_rate = 0.0
                    avg_trade_pct = 0.0
                    best_trade_pct = 0.0
                    worst_trade_pct = 0.0
                    profit_factor = 0.0
                    expectancy = 0.0
                    max_trade_duration = 0
                    avg_trade_duration = 0
            else:
                num_trades = 0
                win_rate = 0.0
                avg_trade_pct = 0.0
                best_trade_pct = 0.0
                worst_trade_pct = 0.0
                profit_factor = 0.0
                expectancy = 0.0
                max_trade_duration = 0
                avg_trade_duration = 0

            # Risk-adjusted return metrics with 6.5% risk-free rate
            RF_RATE = 0.065  # 6.5% per annum

            # Sharpe Ratio: (mean_return - risk_free_rate) / std_dev
            # CAGR is in percentage form, annual_vol is in decimal form
            if annual_vol > 0:
                excess_return = (cagr_pct / 100.0) - RF_RATE
                sharpe_ratio = excess_return / annual_vol
            else:
                sharpe_ratio = 0.0

            # Sortino Ratio: uses downside deviation (calculated from Equity returns)
            downside_returns = daily_equity_returns[daily_equity_returns < 0]
            if len(downside_returns) > 0:
                downside_vol = float(downside_returns.std()) * np.sqrt(245)
                excess_return = (cagr_pct / 100.0) - RF_RATE
                sortino_ratio = (
                    excess_return / downside_vol if downside_vol > 0 else 0.0
                )
            else:
                sortino_ratio = 0.0

            # Calmar Ratio: CAGR / max_drawdown (not adjusted for RF)
            if abs(max_dd_pct) > 0:
                calmar_ratio = (cagr_pct / 100.0) / (abs(max_dd_pct) / 100.0)
            else:
                calmar_ratio = 0.0

            # SQN (System Quality Number): expectancy / standard_dev_pnl
            if len(pnl_values) > 0:
                pnl_std = float(pnl_values.std())
                if pnl_std > 0:
                    sqn = (
                        expectancy / pnl_std * np.sqrt(num_trades)
                        if num_trades > 0
                        else 0.0
                    )
                else:
                    sqn = 0.0
            else:
                sqn = 0.0

            # Kelly Criterion: p * b - q / b, where p=win%, b=avg_win/avg_loss, q=loss%
            if num_trades > 0:
                p = win_rate / 100.0
                win_avg = (
                    pnl_values[pnl_values > 0].mean() if (pnl_values > 0).any() else 0.0
                )
                loss_avg = (
                    abs(pnl_values[pnl_values < 0].mean())
                    if (pnl_values < 0).any()
                    else 1.0
                )
                if loss_avg > 0 and win_avg > 0:
                    b = win_avg / loss_avg
                    kelly_pct = (p * b - (1 - p)) / b
                    kelly_pct = max(0, min(kelly_pct, 1.0))  # clamp to 0-1
                else:
                    kelly_pct = 0.0
            else:
                kelly_pct = 0.0

            # Alpha and Beta calculation using benchmark module
            try:
                alpha_annual, beta, r_squared, stats_dict = calculate_alpha_beta(
                    portfolio_equity=port_df,
                    risk_free_rate=0.06,  # 6% annual risk-free rate
                )
                alpha_pct = alpha_annual * 100  # Convert to percentage
                # Beta is already a ratio, keep as is
            except (BenchmarkError, Exception) as e:
                logger.warning(f"Alpha/Beta calculation failed for {label}: {e}")
                alpha_pct = 0.0  # Fallback to placeholder
                beta = 0.0  # Fallback to placeholder

            # Compile row - keeping only specified columns
            row = {
                "Window": label,
                "Strategy Name": "Ichimoku",  # TODO: pass this as parameter
                "Start": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "End": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "Duration": duration_str,
                "Avg exposure %": round(avg_exposure_pct, 2),
                "Equity Final [INR]": round(equity_end, 2),
                "Net P&L %": round(total_return_pct, 2),
                "CAGR [%]": round(cagr_pct, 2),
                "Sharpe Ratio": round(sharpe_ratio, 2),
                "Sortino Ratio": round(sortino_ratio, 2),
                "Calmar Ratio": round(calmar_ratio, 2),
                "IRR [%]": round(irr_pct, 2),
                "Alpha [%]": round(alpha_pct, 2),
                "Beta": round(beta, 2),
                "Max. Drawdown [%]": round(max_dd_pct, 2),
                "Max. Drawdown Duration": f"{max_dd_duration} days",
                "# Trades": int(num_trades),
                "Win Rate [%]": round(win_rate, 2),
                "Best Trade [%]": round(best_trade_pct, 2),
                "Worst Trade [%]": round(worst_trade_pct, 2),
                "Avg. Trade [%]": round(avg_trade_pct, 2),
                "Max. Trade Duration": f"{max_trade_duration} days",
                "Avg. Trade Duration": f"{avg_trade_duration} days",
                "Profit Factor": (
                    round(profit_factor, 2)
                    if not np.isinf(profit_factor)
                    else float("inf")
                ),
                "Expectancy [%]": round(expectancy, 2),
                "SQN": round(sqn, 2),
                "Kelly Criterion": round(kelly_pct, 4),
            }
            summary_rows.append(row)

        except Exception as e:
            import traceback

            print(f"Error generating summary for {label}: {e}")
            traceback.print_exc()
            continue

    # Write summary CSV
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_csv_path = os.path.join(run_dir, "strategy_backtests_summary.csv")
        summary_df.to_csv(summary_csv_path, index=False)
        return summary_csv_path

    return ""


def run_basket(
    basket_file: str = None,
    strategy_name: str = None,
    params_json: str = None,
    interval: str = None,
    period: str = None,
    windows_years: tuple[int | None, ...] = (1, 3, 5),
    use_cache_only: bool = False,
    cache_dir: str = "cache",
    use_portfolio_csv: bool = False,
    basket_size: str = None,
) -> None:
    """
    Run backtest on a basket of stocks.

    Args:
        basket_file: Path to basket file (if None, uses basket_size)
        basket_size: Size of basket ('mega', 'large', 'mid', 'small') - overrides basket_file
        strategy_name: Name of strategy to use
        params_json: Strategy parameters as JSON string
        interval: Time interval ('1d', '1h', etc.)
        period: Period ('1y', '3y', '5y', 'max')
        windows_years: Analysis windows in years
        use_cache_only: Only use cached data
        cache_dir: Cache directory
        use_portfolio_csv: Generate portfolio CSV
    """
    from config import DEFAULT_BASKET_SIZE, get_basket_file

    # Handle basket selection logic
    if basket_size is not None:
        basket_file = str(get_basket_file(basket_size))
        print(f"📊 Using {basket_size} basket: {basket_file}")
    elif basket_file is None:
        basket_file = str(get_basket_file(DEFAULT_BASKET_SIZE))
        print(f"📊 Using default {DEFAULT_BASKET_SIZE} basket: {basket_file}")
    else:
        print(f"📊 Using specified basket file: {basket_file}")

    bars_per_year = BARS_PER_YEAR_MAP.get(interval, 245)
    bare = _read_symbols_from_txt(basket_file)

    # Try quick path: if we have Dhan CSVs in data/dhan_historical_<SECID>.csv,
    # map each basket symbol -> SECID via data/api-scrip-master-detailed.csv and load the CSVs.
    data_map_full: dict[str, pd.DataFrame] = {}
    try:
        inst_csv = os.path.join("data", "api-scrip-master-detailed.csv")
        if os.path.exists(inst_csv):
            # avoid mixed-type low_memory warnings by reading with low_memory=False
            inst_df = pd.read_csv(inst_csv, low_memory=False)
            for sym in bare:
                # normalize symbol name
                base = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                cand = inst_df[
                    (inst_df["SYMBOL_NAME"] == base)
                    | (inst_df["UNDERLYING_SYMBOL"] == base)
                ]
                if not cand.empty:
                    secid = int(cand.iloc[0]["SECURITY_ID"])
                    csv_path = os.path.join(
                        "data", "cache", f"dhan_historical_{secid}.csv"
                    )
                    if os.path.exists(csv_path):
                        try:
                            df = pd.read_csv(
                                csv_path, parse_dates=["date"], index_col="date"
                            )
                            df.index = pd.to_datetime(df.index)
                            data_map_full[sym] = df.sort_index()
                        except Exception:
                            pass
        # if we loaded nothing, fall back
        if not data_map_full:
            raise RuntimeError("no local Dhan CSVs loaded")
    except Exception:
        # If the quick CSV path failed, allow the loader to read local Dhan CSVs
        # (don't force strict cache-only parquet requirement here).
        data_map_full = load_many_india(
            bare,
            interval=interval,
            period=period,
            cache=True,
            cache_dir=cache_dir,
            use_cache_only=False,
        )

    # Extract basket name from file path for better report naming
    basket_name = "default"
    if basket_file:
        basket_name = os.path.basename(basket_file).replace(".txt", "")
    elif basket_size:
        basket_name = basket_size

    run_dir = make_run_dir(strategy_name=strategy_name, basket_name=basket_name)
    cfg = BrokerConfig()

    # Initialize monitoring
    symbols = list(data_map_full.keys())
    monitor = BacktestMonitor(run_dir, len(symbols))
    print(f"🚀 Starting optimized backtesting for {len(symbols)} symbols...")

    # Check for resume
    remaining_symbols = monitor.get_remaining_symbols(symbols)

    # OPTIMIZATION 1: Run strategy ONCE per symbol (not per window)
    print("⚡ Running strategy once per symbol (5-10x speedup)...")
    symbol_results = {}

    for i, sym in enumerate(remaining_symbols):
        try:
            # Use timeout for individual symbol processing
            with timeout_handler(SYMBOL_TIMEOUT, f"Symbol {sym} processing timed out"):
                monitor.log_progress(sym, "processing")
                logger.info(f"Processing symbol {i+1}/{len(remaining_symbols)}: {sym}")

                df_full = data_map_full[sym]

                # Run strategy ONCE on full data
                strat = make_strategy(strategy_name, params_json)
                trades_full, equity_full, _ = BacktestEngine(df_full, strat, cfg).run()

                # Store results for window processing
                symbol_results[sym] = {
                    "trades": trades_full,
                    "equity": equity_full,
                    "data": df_full,
                }

                monitor.log_progress(sym, "completed")
                logger.debug(f"Successfully processed {sym}")

        except TimeoutError as e:
            logger.warning(f"⚠️ Timeout processing {sym}: {e}")
            monitor.log_progress(sym, "timeout")
            # Continue with next symbol instead of failing entire basket
            continue

        except Exception as e:
            logger.warning(f"⚠️ Error processing {sym}: {e}")
            monitor.log_progress(sym, "error")
            # Continue with next symbol instead of failing entire basket
            continue

        # Monitor resources every 10 symbols
        if i % 10 == 0:
            resources = monitor.monitor_resources()
            print(
                f"💾 Memory: {resources['memory_percent']:.1f}%, CPU: {resources['cpu_percent']:.1f}%"
            )

    # OPTIMIZATION 2: Build all windows from cached results
    print("⚡ Processing time windows from cached results...")
    window_start_time = time.time()
    total_windows = len(windows_years)

    window_results = optimize_window_processing(symbol_results, list(windows_years))

    window_labels: dict[int | None, str] = {1: "1Y", 3: "3Y", 5: "5Y"}
    consolidated_csv_paths: dict[str, str] = {}
    portfolio_csv_paths: dict[str, str] = {}
    window_maxdd: dict[str, float] = {}

    for window_idx, Y in enumerate(windows_years):
        time.time()
        label = window_labels[Y]

        # Progress tracking for window processing
        window_progress = (window_idx / total_windows) * 100
        elapsed_window = time.time() - window_start_time
        eta_window = (
            (elapsed_window / (window_idx + 1)) * (total_windows - window_idx - 1)
            if window_idx > 0
            else 0
        )

        print(
            f"📊 Window Progress: {window_progress:.1f}% ({window_idx + 1}/{total_windows})"
        )
        print(f"⏱️  Window ETA: {eta_window:.1f}s remaining")
        print(f"🔄 Processing {label} window...")

        rows = []

        # Get pre-computed results for this window
        window_data = window_results[label]
        trades_by_symbol = window_data["trades_by_symbol"]
        symbol_equities = {}
        dfs_by_symbol = {}

        for sym in symbol_results.keys():
            df_full = symbol_results[sym]["data"]
            trades = trades_by_symbol[sym]
            equity_full = symbol_results[sym]["equity"]

            # Apply window slicing to data
            df = _slice_df_years(df_full, Y)
            if len(df) == 0:
                continue

            # Filter equity curve to the window
            equity = (
                equity_full.loc[equity_full.index.isin(df.index)]
                if not equity_full.empty
                else equity_full
            )

            row = compute_trade_metrics_table(
                df=df, trades=trades, bars_per_year=bars_per_year
            )
            row["Symbol"] = sym
            row["Window"] = label
            rows.append(row)

            dfs_by_symbol[sym] = df
            symbol_equities[sym] = (
                equity["equity"] if "equity" in equity.columns else equity
            )

        if not rows:
            continue

        # Portfolio curve for the window - fixed equal-weight logic
        # Build portfolio equity curve by aggregating per-trade P&L (realized + MTM) over union of dates.
        # We DO NOT re-allocate initial capital to a single stock. The engine already sized each trade
        # using BrokerConfig.qty_pct_of_equity (5% of initial capital). For portfolio equity we simply
        # sum realized P&L for closed trades and mark-to-market for open trades on each date.
        def _build_portfolio_curve(trades_by_symbol, dfs_by_symbol, initial_capital):
            """Build a daily portfolio curve starting at initial_capital and tracking cumulative realized+unrealized.

            Key principles:
              1. Start at initial_capital on day 0 with zero exposure/returns.
              2. Equity = initial_capital + (sum of closed trade P&L + sum of open trade MTM).
              3. Drawdown = max(0, prev_day_equity - current_equity) — daily drop only.
              4. max_drawdown_inr/pct = running maximum of daily drawdowns.
              5. Last row should match the final equity position, reflecting only settled trades/MTM.

            Output columns: equity, avg_exposure, avg_exposure_pct, realized_inr, realized_pct,
            unrealized_inr, unrealized_pct, total_return_inr, total_return_pct,
            drawdown_inr, drawdown_pct, max_drawdown_inr, max_drawdown_pct.
            """
            # Collect all trading dates from price data
            all_dates = set()
            for df in dfs_by_symbol.values():
                try:
                    idx = pd.to_datetime(df.index)
                    all_dates.update(idx)
                except Exception:
                    continue

            if not all_dates:
                return pd.DataFrame(
                    columns=[
                        "equity",
                        "avg_exposure",
                        "avg_exposure_pct",
                        "realized_inr",
                        "realized_pct",
                        "unrealized_inr",
                        "unrealized_pct",
                        "total_return_inr",
                        "total_return_pct",
                        "drawdown_inr",
                        "drawdown_pct",
                        "max_drawdown_inr",
                        "max_drawdown_pct",
                    ]
                )

            dates = sorted(all_dates)

            # Pre-compute trade events: for each symbol, collect entry/exit times and final P&L
            trade_events = (
                []
            )  # list of (date, sym, "ENTRY"/"EXIT", price, qty, pnl_if_exit)
            for sym, trades in trades_by_symbol.items():
                if trades is None or trades.empty:
                    continue
                for _, tr in trades.reset_index(drop=True).iterrows():
                    try:
                        entry_time = pd.to_datetime(tr.get("entry_time"))
                        entry_price = float(tr.get("entry_price", 0.0))
                        qty = float(tr.get("entry_qty", 0.0))
                        trade_events.append(
                            (entry_time, sym, "ENTRY", entry_price, qty, 0.0, None)
                        )

                        exit_time = tr.get("exit_time")
                        if pd.notna(exit_time):
                            exit_time = pd.to_datetime(exit_time)
                            net_pnl = (
                                float(tr.get("net_pnl", 0.0))
                                if not pd.isna(tr.get("net_pnl"))
                                else 0.0
                            )
                            trade_events.append(
                                (
                                    exit_time,
                                    sym,
                                    "EXIT",
                                    entry_price,
                                    qty,
                                    net_pnl,
                                    None,
                                )
                            )
                    except Exception:
                        continue

            # For each date, compute: which trades are open, which are closed, and their values
            rows = []
            prev_equity = float(initial_capital)
            max_dd_inr = 0.0
            max_dd_pct = 0.0

            # Pre-calculate cumulative realized P&L timeline to avoid double-counting
            # For each date, calculate the cumulative P&L from all trades closed by that date
            realized_pnl_by_date = {}
            realized_entry_amounts_by_date = (
                {}
            )  # Track actual entry amounts for % calculation
            for sym, trades in trades_by_symbol.items():
                if trades is None or trades.empty:
                    continue
                # Vectorized approach for realized P&L calculation
                trades_copy = trades.copy()
                trades_copy["exit_time"] = pd.to_datetime(
                    trades_copy["exit_time"], errors="coerce"
                )
                trades_copy["net_pnl"] = pd.to_numeric(
                    trades_copy["net_pnl"], errors="coerce"
                ).fillna(0.0)

                # Filter trades with valid exit times
                exited_trades = trades_copy[trades_copy["exit_time"].notna()]

                if not exited_trades.empty:
                    # Calculate entry amounts (entry_price * quantity) for realized P&L %
                    # Use the correct column names
                    qty_col = (
                        "Position size (qty)"
                        if "Position size (qty)" in exited_trades.columns
                        else "entry_qty"
                    )
                    price_col = (
                        "entry_price"
                        if "entry_price" in exited_trades.columns
                        else "Price INR"
                    )
                    exited_trades = (
                        exited_trades.copy()
                    )  # Create explicit copy to avoid warning
                    exited_trades.loc[:, "entry_amount"] = pd.to_numeric(
                        exited_trades[price_col], errors="coerce"
                    ).fillna(0.0) * pd.to_numeric(
                        exited_trades[qty_col], errors="coerce"
                    ).fillna(
                        0.0
                    )

                    # Group by exit date and sum P&L and entry amounts
                    pnl_by_date = exited_trades.groupby("exit_time")["net_pnl"].sum()
                    amounts_by_date = exited_trades.groupby("exit_time")[
                        "entry_amount"
                    ].sum()

                    for exit_dt, net_pnl in pnl_by_date.items():
                        if exit_dt not in realized_pnl_by_date:
                            realized_pnl_by_date[exit_dt] = 0.0
                        realized_pnl_by_date[exit_dt] += net_pnl

                    for exit_dt, entry_amount in amounts_by_date.items():
                        if exit_dt not in realized_entry_amounts_by_date:
                            realized_entry_amounts_by_date[exit_dt] = 0.0
                        realized_entry_amounts_by_date[exit_dt] += entry_amount

            # Build cumulative realized P&L for each date
            realized_cum_total = 0.0
            prev_unrealized = 0.0

            for dt in dates:
                # Add any realized P&L that occurred on this date
                dt_obj = pd.to_datetime(dt)
                daily_realized = 0.0
                if dt_obj in realized_pnl_by_date:
                    daily_realized = realized_pnl_by_date[dt_obj]
                    realized_cum_total += daily_realized

                # Calculate daily unrealized P&L from open trades
                unrealized = 0.0
                exposure = 0.0

                for sym, trades in trades_by_symbol.items():
                    if trades is None or trades.empty:
                        continue
                    df = dfs_by_symbol.get(sym)
                    if df is None or df.empty:
                        continue

                    # Get price at or before this date
                    try:
                        sel = df.loc[:dt]
                        if sel.empty:
                            continue
                        price_at_dt = float(sel["close"].iloc[-1])
                    except Exception:
                        price_at_dt = None

                    # Vectorized approach instead of iterrows() for better performance
                    if not trades.empty:
                        dt_obj = pd.to_datetime(dt)
                        trades_copy = trades.copy()

                        # Check if required columns exist
                        required_cols = [
                            "entry_time",
                            "exit_time",
                            "entry_price",
                            "entry_qty",
                        ]
                        missing_cols = [
                            col
                            for col in required_cols
                            if col not in trades_copy.columns
                        ]

                        if missing_cols:
                            print(
                                f"Warning: Missing columns {missing_cols} in trades for {sym}. Available columns: {list(trades_copy.columns)}"
                            )
                            continue

                        # Convert times to datetime with error handling
                        try:
                            trades_copy["entry_time"] = pd.to_datetime(
                                trades_copy["entry_time"], errors="coerce"
                            )
                            trades_copy["exit_time"] = pd.to_datetime(
                                trades_copy["exit_time"], errors="coerce"
                            )

                            # Convert price and qty to numeric
                            trades_copy["entry_price"] = pd.to_numeric(
                                trades_copy["entry_price"], errors="coerce"
                            ).fillna(0.0)
                            trades_copy["entry_qty"] = pd.to_numeric(
                                trades_copy["entry_qty"], errors="coerce"
                            ).fillna(0.0)
                        except Exception as e:
                            print(
                                f"Warning: Error converting trade data for {sym}: {e}"
                            )
                            continue

                        # Filter trades that have entered by this date with robust datetime handling
                        try:
                            # Ensure dt_obj is timezone-naive if entry_time is timezone-naive
                            if (
                                hasattr(trades_copy["entry_time"].iloc[0], "tz")
                                and trades_copy["entry_time"].iloc[0].tz is not None
                            ):
                                if dt_obj.tz is None:
                                    dt_obj = dt_obj.tz_localize("UTC")
                            else:
                                if hasattr(dt_obj, "tz") and dt_obj.tz is not None:
                                    dt_obj = dt_obj.tz_localize(None)

                            # Remove any NaT values before comparison
                            valid_entry_mask = trades_copy["entry_time"].notna()
                            if not valid_entry_mask.any():
                                continue

                            # More efficient filtering to avoid memory issues
                            try:
                                # Apply both filters in one operation to reduce memory usage
                                time_mask = trades_copy["entry_time"] <= dt_obj
                                combined_mask = valid_entry_mask & time_mask
                                entered_trades = trades_copy.loc[combined_mask].copy()
                            except (MemoryError, KeyboardInterrupt):
                                # Fallback to simpler approach if memory issues
                                valid_trades = trades_copy.dropna(subset=["entry_time"])
                                time_filter = valid_trades["entry_time"] <= dt_obj
                                entered_trades = valid_trades[time_filter]
                        except Exception as e:
                            print(
                                f"Warning: Error filtering trades by entry_time for {sym}: {e}"
                            )
                            continue

                        if not entered_trades.empty:
                            # Identify open trades (no exit or exit after current date)
                            open_mask = (entered_trades["exit_time"].isna()) | (
                                entered_trades["exit_time"] > dt_obj
                            )
                            open_trades = entered_trades[open_mask]

                            if not open_trades.empty and price_at_dt is not None:
                                # Calculate MTM for all open trades with robust error handling
                                try:
                                    entry_day_mask = open_trades["entry_time"] == dt_obj

                                    # Entry day trades: MTM = 0, use entry price for exposure
                                    entry_day_trades = open_trades[entry_day_mask]
                                    if not entry_day_trades.empty:
                                        # Ensure numeric types and handle NaN values
                                        entry_prices = pd.to_numeric(
                                            entry_day_trades["entry_price"],
                                            errors="coerce",
                                        ).fillna(0.0)
                                        entry_qtys = pd.to_numeric(
                                            entry_day_trades["entry_qty"],
                                            errors="coerce",
                                        ).fillna(0.0)
                                        exposure_value = abs(
                                            entry_prices * entry_qtys
                                        ).sum()
                                        if not pd.isna(exposure_value):
                                            exposure += exposure_value

                                    # Post-entry trades: MTM based on current price vs entry price
                                    post_entry_trades = open_trades[~entry_day_mask]
                                    if not post_entry_trades.empty:
                                        # Ensure numeric types and handle NaN values
                                        post_entry_prices = pd.to_numeric(
                                            post_entry_trades["entry_price"],
                                            errors="coerce",
                                        ).fillna(0.0)
                                        post_entry_qtys = pd.to_numeric(
                                            post_entry_trades["entry_qty"],
                                            errors="coerce",
                                        ).fillna(0.0)

                                        mtm_values = (
                                            price_at_dt - post_entry_prices
                                        ) * post_entry_qtys
                                        mtm_sum = mtm_values.sum()
                                        if not pd.isna(mtm_sum):
                                            unrealized += mtm_sum

                                        exposure_value = abs(
                                            price_at_dt * post_entry_qtys
                                        ).sum()
                                        if not pd.isna(exposure_value):
                                            exposure += exposure_value

                                except Exception as e:
                                    print(
                                        f"Warning: Error calculating MTM for {sym}: {e}"
                                    )
                                    continue

                # Equity is always initial_capital + (realized + unrealized)
                total_return = realized_cum_total + unrealized
                equity_val = float(initial_capital) + total_return

                # Drawdown is daily drop from previous day
                draw_inr = max(0.0, prev_equity - equity_val)
                draw_pct = (draw_inr / prev_equity * 100.0) if prev_equity > 0 else 0.0

                # Update running max drawdown
                if draw_inr > max_dd_inr:
                    max_dd_inr = draw_inr
                    max_dd_pct = draw_pct

                # Calculate incremental changes for this day/period
                daily_realized_increment = (
                    daily_realized  # This is already the daily increment
                )
                daily_unrealized_increment = (
                    unrealized - prev_unrealized
                )  # Change in unrealized MTM
                daily_total_increment = (
                    daily_realized_increment + daily_unrealized_increment
                )

                # Calculate percentage based on current equity as denominator
                # Realized % based on current equity
                realized_pct = (
                    (daily_realized_increment / equity_val * 100.0)
                    if equity_val > 0
                    else 0.0
                )

                # Unrealized % based on current equity
                unrealized_pct = (
                    (daily_unrealized_increment / equity_val * 100.0)
                    if equity_val > 0
                    else 0.0
                )

                # Total % based on current equity
                total_pct = (
                    (daily_total_increment / equity_val * 100.0)
                    if equity_val > 0
                    else 0.0
                )

                # Update avg_exposure_pct to be relative to current equity
                avg_exposure_pct = (
                    (exposure / equity_val * 100.0) if equity_val > 0 else 0.0
                )

                rows.append(
                    {
                        "time": pd.to_datetime(dt),
                        "equity": equity_val,
                        "avg_exposure": exposure,
                        "avg_exposure_pct": avg_exposure_pct,
                        "realized_inr": daily_realized_increment,  # Daily incremental realized P&L
                        "realized_pct": realized_pct,
                        "unrealized_inr": daily_unrealized_increment,  # Daily incremental unrealized change
                        "unrealized_pct": unrealized_pct,
                        "total_return_inr": daily_total_increment,  # Daily incremental total
                        "total_return_pct": total_pct,
                        "drawdown_inr": draw_inr,
                        "drawdown_pct": draw_pct,
                        "max_drawdown_inr": max_dd_inr,
                        "max_drawdown_pct": max_dd_pct,
                    }
                )

                # Update previous values for next iteration
                prev_unrealized = unrealized

                prev_equity = equity_val

            df_port = pd.DataFrame(rows).set_index("time").sort_index()

            # Prepend explicit initial-capital baseline on first date
            if not df_port.empty:
                first_dt = df_port.index[0]
                first_row_data = {
                    "equity": float(initial_capital),
                    "avg_exposure": 0.0,
                    "avg_exposure_pct": 0.0,
                    "realized_inr": 0.0,
                    "realized_pct": 0.0,
                    "unrealized_inr": 0.0,
                    "unrealized_pct": 0.0,
                    "total_return_inr": 0.0,
                    "total_return_pct": 0.0,
                    "drawdown_inr": 0.0,
                    "drawdown_pct": 0.0,
                    "max_drawdown_inr": 0.0,
                    "max_drawdown_pct": 0.0,
                }
                first_baseline_df = pd.DataFrame([first_row_data], index=[first_dt])
                # Combine, keeping first occurrence if dates match
                df_port = pd.concat([first_baseline_df, df_port])
                df_port = df_port[~df_port.index.duplicated(keep="first")].sort_index()

            return df_port

        port_df = _build_portfolio_curve(
            trades_by_symbol, dfs_by_symbol, cfg.initial_capital
        )
        if not port_df.empty and "max_drawdown_pct" in port_df.columns:
            try:
                window_maxdd[label] = float(
                    pd.to_numeric(port_df["max_drawdown_pct"], errors="coerce").max()
                )
            except Exception:
                window_maxdd[label] = 0.0
        else:
            window_maxdd[label] = 0.0

        # TOTAL row: compute portfolio-level metrics using user's trade-aggregation formula
        # NOTE: do NOT append the TOTAL into `rows` here; we'll compute and
        # inject a single TOTAL row later when building the output table to
        # avoid producing duplicate TOTAL rows.
        total_row = compute_portfolio_trade_metrics(
            dfs_by_symbol=dfs_by_symbol,
            trades_by_symbol=trades_by_symbol,
            bars_per_year=bars_per_year,
        )
        total_row["Symbol"] = "TOTAL"
        total_row["Window"] = label

        # Build per-window parameter table (per-symbol rows) and a portfolio TOTAL row.
        # We'll produce a single CSV `basket_{label}.csv` with the requested columns
        # and put the TOTAL row at the top.
        try:
            params_rows = []
            for r in rows:
                sym = r.get("Symbol")
                # compute additional fields: Net P&L % (equity pct change) and Max equity drawdown
                net_pnl_pct = 0.0
                maxdd = 0.0

                # Always use equity-based calculation for Net P&L % to match CAGR calculation
                # This ensures both metrics use the same equity data and are consistent
                eqs = symbol_equities.get(sym)
                if eqs is not None and not eqs.empty:
                    try:
                        start_eq = float(eqs.iloc[0])
                        end_eq = float(eqs.iloc[-1])
                        net_pnl_pct = (
                            (end_eq / start_eq - 1.0) * 100.0 if start_eq != 0 else 0.0
                        )
                    except Exception:
                        net_pnl_pct = 0.0

                # Calculate max drawdown using highest individual trade drawdown
                # This is more meaningful than equity curve drawdown as it represents actual trading risk
                trades_df = trades_by_symbol.get(sym)
                if trades_df is not None and not trades_df.empty:
                    # Get all trade drawdowns and find the maximum
                    try:
                        # For each trade, calculate drawdown based on entry price vs lowest price during trade
                        max_trade_dd = 0.0
                        for _, trade in trades_df.iterrows():
                            entry_time = trade.get("entry_time")
                            exit_time = trade.get("exit_time")
                            entry_price = trade.get("entry_price", 0)

                            if entry_time and exit_time and entry_price > 0:
                                # Get price data during trade period
                                symbol_df = dfs_by_symbol.get(sym)
                                if symbol_df is not None and not symbol_df.empty:
                                    trade_data = symbol_df.loc[
                                        (symbol_df.index >= entry_time)
                                        & (symbol_df.index <= exit_time)
                                    ]
                                    if (
                                        not trade_data.empty
                                        and "low" in trade_data.columns
                                    ):
                                        min_low = trade_data["low"].min()
                                        trade_dd = (
                                            (entry_price - min_low) / entry_price * 100
                                            if entry_price > 0
                                            else 0
                                        )
                                        max_trade_dd = max(max_trade_dd, trade_dd)

                        maxdd = float(max_trade_dd)
                    except Exception:
                        maxdd = 0.0
                else:
                    net_pnl_pct = 0.0
                    maxdd = 0.0

                # compute per-symbol Equity CAGR (%) when symbol equity is present
                eq_cagr_pct = 0.0
                try:
                    eqs = symbol_equities.get(sym)
                    if eqs is not None and not eqs.empty:
                        start_eq = float(eqs.iloc[0])
                        end_eq = float(eqs.iloc[-1])

                        # For windowed analysis (1Y, 3Y, 5Y), use the window period as n_years
                        # to ensure CAGR represents true annualized return for the specified window
                        if Y is not None:
                            n_years = (
                                Y  # Use the window period directly (1, 3, or 5 years)
                            )
                        else:
                            # For "ALL" window, calculate from actual dates
                            idx = eqs.index
                            if (
                                hasattr(idx, "dtype")
                                and "datetime" in str(idx.dtype).lower()
                            ):
                                days = (
                                    pd.to_datetime(idx[-1]) - pd.to_datetime(idx[0])
                                ).days
                                n_years = max(days / 365.25, 1 / 365.25)
                            else:
                                n_years = 1.0

                        eq_cagr_pct = (
                            ((end_eq / start_eq) ** (1.0 / n_years) - 1.0) * 100.0
                            if start_eq > 0
                            else 0.0
                        )
                except Exception:
                    eq_cagr_pct = 0.0

                row_out = {
                    "Window": r.get("Window"),
                    "Symbol": sym,
                    "Net P&L %": net_pnl_pct,
                    "Max equity drawdown %": maxdd,
                    "Total trades": r.get("NumTrades", 0),
                    "Profitable trades %": r.get("WinRatePct", 0.0),
                    "Profit factor": r.get("ProfitFactor", 0.0),
                    "Avg P&L % per trade": r.get("AvgProfitPerTradePct", 0.0),
                    "Avg bars per trade": r.get("AvgBarsPerTrade", float("nan")),
                    # IRR_pct provided by compute_trade_metrics_table (trade/deployment-based)
                    "IRR %": r.get("IRR_pct", 0.0),
                    # CAGR will be populated from equity series in reporting (for TOTAL we compute below)
                    "Equity CAGR %": eq_cagr_pct,
                }
                params_rows.append(row_out)

            # Compute portfolio TOTAL row
            total_row = compute_portfolio_trade_metrics(
                dfs_by_symbol, trades_by_symbol, bars_per_year
            )
            # compute portfolio Net P&L %, MaxDD, and CAGR from port_df
            try:
                port_net_pct = 0.0
                port_maxdd = 0.0
                equity_cagr = 0.0

                if not port_df.empty:
                    # Extract start and end equity
                    try:
                        start_eq = float(port_df["equity"].iloc[0])
                        end_eq = float(port_df["equity"].iloc[-1])
                        port_net_pct = (
                            (end_eq / start_eq - 1.0) * 100.0 if start_eq != 0 else 0.0
                        )
                    except Exception:
                        port_net_pct = 0.0

                    # Max drawdown comes directly from port_df's max_drawdown_pct column (portfolio-level)
                    try:
                        port_maxdd = float(
                            pd.to_numeric(
                                port_df["max_drawdown_pct"], errors="coerce"
                            ).max()
                        )
                    except Exception:
                        port_maxdd = 0.0

                    # Compute CAGR based on time span
                    try:
                        # For windowed analysis (1Y, 3Y, 5Y), use the window period as n_years
                        # to ensure CAGR represents true annualized return for the specified window
                        if Y is not None:
                            n_years = (
                                Y  # Use the window period directly (1, 3, or 5 years)
                            )
                        else:
                            # For "ALL" window, calculate from actual dates
                            idx_dates = pd.to_datetime(port_df.index)
                            if len(idx_dates) >= 2:
                                days = (idx_dates[-1] - idx_dates[0]).days
                                n_years = max(days / 365.25, 1.0 / 365.25)
                            else:
                                n_years = 1.0

                        equity_cagr = (
                            ((end_eq / start_eq) ** (1.0 / n_years) - 1.0)
                            if start_eq > 0
                            else 0.0
                        )
                    except Exception:
                        equity_cagr = 0.0
            except Exception:
                port_net_pct = 0.0
                port_maxdd = 0.0
                equity_cagr = 0.0

            total_row_out = {
                "Window": label,
                "Symbol": "TOTAL",
                "Net P&L %": port_net_pct,
                "Max equity drawdown %": port_maxdd,
                "Total trades": int(total_row.get("NumTrades", 0)),
                "Profitable trades %": float(total_row.get("WinRatePct", 0.0)),
                "Profit factor": float(total_row.get("ProfitFactor", 0.0)),
                "Avg P&L % per trade": float(
                    total_row.get("AvgProfitPerTradePct", 0.0)
                ),
                "Avg bars per trade": float(
                    total_row.get("AvgBarsPerTrade", float("nan"))
                ),
                "IRR %": float(total_row.get("IRR_pct", 0.0)),
                # Equity CAGR in percent
                "Equity CAGR %": float(equity_cagr * 100.0),
            }

            # Build DataFrame with TOTAL first, then symbols sorted
            params_df = pd.DataFrame(params_rows)
            # remove duplicates and ensure consistent ordering
            params_df = params_df.sort_values(by=["Symbol"]).reset_index(drop=True)
            final_df = pd.concat(
                [pd.DataFrame([total_row_out]), params_df], ignore_index=True
            )

            # Write CSV with portfolio key metrics (renamed from basket)
            csv_path = os.path.join(run_dir, f"portfolio_key_metrics_{label}.csv")

            # Format percent fields as numeric (two decimals, no '%' suffix)
            pct_cols = [
                "Net P&L %",
                "Profitable trades %",
                "Avg P&L % per trade",
                "IRR %",
                "Equity CAGR %",
                "Max equity drawdown %",
            ]
            for col in pct_cols:
                if col in final_df.columns:
                    final_df[col] = (
                        pd.to_numeric(final_df[col], errors="coerce")
                        .fillna(0.0)
                        .apply(lambda v: round(float(v), 2))
                    )

            # Profit factor: numeric rounded to 2 decimals
            if "Profit factor" in final_df.columns:
                import math

                def _fmt_pf_num(v):
                    try:
                        if v is None:
                            return 0.0
                        fv = float(v)
                        if math.isnan(fv):
                            return 0.0
                        if not math.isfinite(fv):
                            return float("inf")
                        return round(fv, 2)
                    except Exception:
                        return 0.0

                final_df["Profit factor"] = final_df["Profit factor"].apply(_fmt_pf_num)

            # Avg bars per trade should be integer
            if "Avg bars per trade" in final_df.columns:
                try:
                    final_df["Avg bars per trade"] = (
                        pd.to_numeric(final_df["Avg bars per trade"], errors="coerce")
                        .fillna(0)
                        .astype(int)
                    )
                except Exception:
                    final_df["Avg bars per trade"] = final_df[
                        "Avg bars per trade"
                    ].apply(lambda v: int(float(v)) if v not in (None, "") else 0)

            # Ensure Total trades is integer
            if "Total trades" in final_df.columns:
                final_df["Total trades"] = (
                    pd.to_numeric(final_df["Total trades"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )

            # Write CSV
            final_df.to_csv(csv_path, index=False)
            consolidated_csv_paths[label] = csv_path

            # Consolidated trades-only CSV (all symbols concatenated) with requested columns
            trades_list = [
                t.reset_index(drop=True).assign(Symbol=sym)
                for sym, t in trades_by_symbol.items()
                if t is not None and not t.empty
            ]

            if trades_list:
                # Filter out any None, empty, or all-NA entries before concatenation to avoid FutureWarning
                valid_trades_list = []
                for t in trades_list:
                    if (
                        t is not None
                        and not t.empty
                        and not t.isna().all().all()
                        and len(t.dropna(how="all", axis=1)) > 0
                    ):  # Remove all-NA columns
                        # Clean the DataFrame by removing all-NA columns
                        clean_t = t.dropna(how="all", axis=1)
                        if not clean_t.empty:
                            valid_trades_list.append(clean_t)

                if valid_trades_list:
                    trades_only_df = pd.concat(
                        valid_trades_list, axis=0, ignore_index=True
                    )
                else:
                    trades_only_df = (
                        pd.DataFrame()
                    )  # Empty DataFrame if no valid trades

                # normalize and compute requested columns and ordering
                # Ensure datetime columns are stringified consistently

                trades_only_df["entry_time"] = pd.to_datetime(
                    trades_only_df.get("entry_time")
                )
                trades_only_df["exit_time"] = pd.to_datetime(
                    trades_only_df.get("exit_time")
                )

                # Create TV-style rows (Exit then Entry) per trade to match prior format
                tv_rows = []

                # Simplified approach - just create basic trade records
                for i, tr in trades_only_df.reset_index(drop=True).iterrows():
                    try:
                        trade_no = i + 1

                        # Safe extraction with defaults
                        entry_time = tr.get("entry_time", "")
                        exit_time = tr.get("exit_time", "")
                        entry_price = tr.get("entry_price", 0)
                        exit_price = tr.get("exit_price", 0)
                        qty = tr.get("entry_qty", 0)
                        net_pnl = tr.get("net_pnl", 0)
                        exit_reason = tr.get("exit_reason", "signal")
                        symbol = tr.get("Symbol", "")

                        # Convert to safe types
                        try:
                            entry_price = (
                                float(entry_price)
                                if entry_price and not pd.isna(entry_price)
                                else 0
                            )
                            exit_price = (
                                float(exit_price)
                                if exit_price and not pd.isna(exit_price)
                                else 0
                            )
                            qty = int(qty) if qty and not pd.isna(qty) else 0
                            net_pnl = (
                                float(net_pnl)
                                if net_pnl and not pd.isna(net_pnl)
                                else 0
                            )
                            entry_time = (
                                pd.to_datetime(entry_time) if entry_time else None
                            )
                            exit_time = pd.to_datetime(exit_time) if exit_time else None
                        except Exception:
                            entry_price = exit_price = qty = net_pnl = 0
                            entry_time = exit_time = None

                        # Calculate missing metrics
                        position_value = entry_price * qty if entry_price and qty else 0
                        net_pnl_pct = (
                            (net_pnl / position_value * 100)
                            if position_value > 0
                            else 0
                        )

                        # Calculate run-up and drawdown using OHLC data during trade period
                        runup_inr = runup_pct = drawdown_inr = drawdown_pct = 0

                        if entry_time and exit_time and symbol and entry_price > 0:
                            # Get OHLC data for this symbol during trade period
                            symbol_df = dfs_by_symbol.get(symbol)
                            if symbol_df is not None and not symbol_df.empty:
                                # Filter data between entry and exit (inclusive)
                                trade_data = symbol_df.loc[
                                    (symbol_df.index >= entry_time)
                                    & (symbol_df.index <= exit_time)
                                ]

                                if (
                                    not trade_data.empty
                                    and "high" in trade_data.columns
                                    and "low" in trade_data.columns
                                ):
                                    # Run-up: Maximum favorable movement (highest high - entry price)
                                    max_high = trade_data["high"].max()
                                    runup_inr = max(0, (max_high - entry_price) * qty)
                                    runup_pct = (
                                        max(
                                            0,
                                            (max_high - entry_price)
                                            / entry_price
                                            * 100,
                                        )
                                        if entry_price > 0
                                        else 0
                                    )

                                    # Drawdown: Maximum adverse movement (entry price - lowest low)
                                    min_low = trade_data["low"].min()
                                    drawdown_inr = max(0, (entry_price - min_low) * qty)
                                    drawdown_pct = (
                                        max(
                                            0,
                                            (entry_price - min_low) / entry_price * 100,
                                        )
                                        if entry_price > 0
                                        else 0
                                    )

                        # Create signal text based on exit reason
                        if exit_reason == "stop":
                            signal_text = "Stop loss exit"
                        else:
                            signal_text = "Close entry(s) order LONG"

                        # Format dates safely
                        if pd.isna(entry_time) or entry_time is None:
                            entry_str = ""
                        else:
                            entry_str = (
                                entry_time.strftime("%Y-%m-%d")
                                if hasattr(entry_time, "strftime")
                                else str(entry_time)
                            )

                        if pd.isna(exit_time) or exit_time is None:
                            exit_str = ""
                        else:
                            exit_str = (
                                exit_time.strftime("%Y-%m-%d")
                                if hasattr(exit_time, "strftime")
                                else str(exit_time)
                            )

                        # Exit row
                        tv_rows.append(
                            {
                                "Trade #": trade_no,
                                "Type": "Exit long",
                                "Date/Time": exit_str,
                                "Signal": signal_text,
                                "Price INR": int(exit_price) if exit_price > 0 else "",
                                "Position size (qty)": int(qty) if qty > 0 else "",
                                "Position size (value)": (
                                    int(exit_price * qty)
                                    if exit_price > 0 and qty > 0
                                    else ""
                                ),
                                "Net P&L INR": int(net_pnl) if net_pnl != 0 else 0,
                                "Net P&L %": (
                                    f"{net_pnl_pct:.2f}%"
                                    if net_pnl_pct != 0
                                    else "0.00%"
                                ),
                                "Run-up INR": int(runup_inr) if runup_inr > 0 else 0,
                                "Run-up %": (
                                    f"{runup_pct:.2f}%" if runup_pct > 0 else "0.00%"
                                ),
                                "Drawdown INR": (
                                    f"-{int(drawdown_inr)}" if drawdown_inr > 0 else 0
                                ),
                                "Drawdown %": (
                                    f"-{drawdown_pct:.2f}%"
                                    if drawdown_pct > 0
                                    else "0.00%"
                                ),
                                "Cumulative P&L INR": "",
                                "Cumulative P&L %": "",
                            }
                        )

                        # Entry row
                        tv_rows.append(
                            {
                                "Trade #": trade_no,
                                "Type": "Entry long",
                                "Date/Time": entry_str,
                                "Signal": "LONG",
                                "Price INR": int(entry_price) if entry_price else "",
                                "Position size (qty)": int(qty) if qty else "",
                                "Position size (value)": (
                                    int(entry_price * qty)
                                    if entry_price and qty
                                    else ""
                                ),
                                "Net P&L INR": "",
                                "Net P&L %": "",
                                "Run-up INR": "",
                                "Run-up %": "",
                                "Drawdown INR": "",
                                "Drawdown %": "",
                                "Cumulative P&L INR": "",
                                "Cumulative P&L %": "",
                            }
                        )

                    except Exception as e:
                        print(f"DEBUG {label}: error processing trade {i}: {e}")
                        continue

                print(
                    f"DEBUG {label}: created {len(tv_rows)} TV rows from {len(trades_only_df)} trades"
                )

                trades_only_out = pd.DataFrame(tv_rows)

                # Assign Symbol where possible (map trade number -> symbol)
                trade_to_sym = {}
                current_trade_no = 1
                for sym, t in trades_by_symbol.items():
                    if t is None or t.empty:
                        continue
                    for _ in t.reset_index(drop=True).itertuples():
                        trade_to_sym[current_trade_no] = sym
                        current_trade_no += 1

                print(
                    f"DEBUG {label}: trade_to_sym mapping has {len(trade_to_sym)} entries"
                )
                trades_only_out["Symbol"] = trades_only_out["Trade #"].map(trade_to_sym)

                # Ensure numeric Net P&L INR and Position size (value)
                trades_only_out["Net P&L INR"] = pd.to_numeric(
                    trades_only_out["Net P&L INR"], errors="coerce"
                )
                trades_only_out["Position size (value)"] = pd.to_numeric(
                    trades_only_out["Position size (value)"], errors="coerce"
                )
                # Write out with requested column order
                # Put Symbol as the second column as requested
                cols = [
                    "Trade #",
                    "Symbol",
                    "Type",
                    "Date/Time",
                    "Signal",
                    "Price INR",
                    "Position size (qty)",
                    "Position size (value)",
                    "Net P&L INR",
                    "Net P&L %",
                    "Run-up INR",
                    "Run-up %",
                    "Drawdown INR",
                    "Drawdown %",
                ]
                trades_only_path = os.path.join(
                    run_dir, f"consolidated_trades_{label}.csv"
                )
                trades_only_out = trades_only_out.reindex(columns=cols)
                print(
                    f"DEBUG {label}: writing consolidated trades to {trades_only_path}"
                )
                trades_only_out.to_csv(trades_only_path, index=False, columns=cols)
                consolidated_csv_paths[f"trades_{label}"] = trades_only_path
                print(f"DEBUG {label}: successfully wrote consolidated trades file")

            # Save portfolio (TOTAL) consolidated csv path as portfolio curve path
            # We'll emit distinct daily and monthly portfolio files below; keep a legacy copy for compatibility.
            print(
                f"DEBUG {label}: starting portfolio curve generation, port_df shape: {port_df.shape if not port_df.empty else 'empty'}"
            )
            try:
                # write daily consolidated curve CSV (daily values)
                # Write daily consolidated curve into consolidated_{label}.csv
                # Create a numeric daily DataFrame from port_df
                try:
                    # port_df contains 'equity' and drawdown columns named 'drawdown_inr','drawdown_pct', etc.
                    df_daily_num = port_df.reset_index().rename(
                        columns={"index": "time", "equity": "Equity"}
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])
                except Exception:
                    df_daily_num = port_df.reset_index()
                    df_daily_num.columns = (
                        ["time", "Equity"] + list(df_daily_num.columns[2:])
                        if df_daily_num.shape[1] >= 2
                        else df_daily_num.columns
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])

                # Prepare display versions (Equity integer, drawdown as percent string)
                df_daily_display = df_daily_num.copy()
                try:
                    df_daily_display["Equity"] = (
                        df_daily_display["Equity"].astype(float).round(0).astype(int)
                    )
                except Exception:
                    df_daily_display["Equity"] = df_daily_display["Equity"].apply(
                        lambda v: int(round(float(v))) if pd.notna(v) else 0
                    )
                # Ensure drawdown percent numeric field exists (drawdown_pct). Port_df uses 'drawdown_pct'
                if "drawdown_pct" in df_daily_display.columns:
                    try:
                        df_daily_display["drawdown_pct"] = (
                            pd.to_numeric(
                                df_daily_display["drawdown_pct"],
                                errors="coerce",
                            )
                            .fillna(0.0)
                            .apply(lambda v: round(float(v), 2))
                        )
                    except Exception:
                        df_daily_display["drawdown_pct"] = df_daily_display[
                            "drawdown_pct"
                        ].apply(lambda v: round(float(v), 2) if pd.notna(v) else 0.0)
                else:
                    # best-effort: if 'drawdown_inr' and Equity are present, compute percent
                    try:
                        draw_inr = pd.to_numeric(
                            df_daily_display.get("drawdown_inr", 0), errors="coerce"
                        ).fillna(0.0)
                        eq_val = pd.to_numeric(
                            df_daily_display.get("Equity", cfg.initial_capital),
                            errors="coerce",
                        ).replace({0: cfg.initial_capital})
                        df_daily_display["drawdown_pct"] = (
                            draw_inr / eq_val * 100.0
                        ).apply(lambda v: round(float(v), 2))
                    except Exception:
                        df_daily_display["drawdown_pct"] = 0.0

                # create numeric daily dataframe from port_df
                try:
                    df_daily_num = port_df.reset_index().rename(
                        columns={
                            "index": "time",
                            "equity": "Equity",
                            "drawdown": "drawdown",
                        }
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])
                except Exception:
                    df_daily_num = port_df.reset_index()
                    df_daily_num.columns = (
                        ["time", "Equity", "drawdown"]
                        if df_daily_num.shape[1] >= 3
                        else df_daily_num.columns
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])

                # Format numeric columns (note: df_daily_display was already prepared and renamed above)
                try:
                    df_daily_display["Equity"] = (
                        df_daily_display["Equity"].astype(float).round(0).astype(int)
                    )
                except Exception:
                    df_daily_display["Equity"] = df_daily_display["Equity"].apply(
                        lambda v: int(round(float(v))) if pd.notna(v) else 0
                    )

                # Round INR columns to integers
                inr_cols = [
                    "avg_exposure",
                    "realized_inr",
                    "unrealized_inr",
                    "total_return_inr",
                    "drawdown_inr",
                    "max_drawdown_inr",
                ]
                for c in inr_cols:
                    if c in df_daily_display.columns:
                        df_daily_display[c] = (
                            pd.to_numeric(df_daily_display[c], errors="coerce")
                            .fillna(0)
                            .apply(lambda v: int(round(float(v))))
                        )

                # Percent columns: numeric floats with 2 decimals (no '%' suffix),
                # matching the user's example files where percent columns are numeric.
                pct_cols = {
                    "avg_exposure_pct": "Avg exposure %",
                    "realized_pct": "Realized %",
                    "unrealized_pct": "Unrealized %",
                    "total_return_pct": "Total Return %",
                    "drawdown_pct": "Drawdown %",
                    "max_drawdown_pct": "Max drawdown %",
                }
                for src, dst in pct_cols.items():
                    if src in df_daily_display.columns:
                        df_daily_display[dst] = (
                            pd.to_numeric(df_daily_display[src], errors="coerce")
                            .fillna(0.0)
                            .apply(lambda v: round(float(v), 2))
                        )

                # Rename and select final daily columns in requested order
                df_daily_display = df_daily_display.reset_index(drop=True)
                # ensure all expected cols exist
                for k in [
                    "avg_exposure",
                    "avg_exposure_pct",
                    "realized_inr",
                    "realized_pct",
                    "unrealized_inr",
                    "unrealized_pct",
                    "total_return_inr",
                    "total_return_pct",
                    "max_drawdown_inr",
                    "max_drawdown_pct",
                ]:
                    if k not in df_daily_display.columns:
                        df_daily_display[k] = 0

                df_daily_display = df_daily_display.rename(
                    columns={
                        "time": "Date",
                        "Equity": "Equity",
                        "avg_exposure": "Avg exposure",
                        "realized_inr": "Realized INR",
                        "unrealized_inr": "Unrealized INR",
                        "total_return_inr": "Total Return INR",
                        "max_drawdown_inr": "Max drawdown INR",
                    }
                )

                # Add percent columns if not present already
                if "Avg exposure %" not in df_daily_display.columns:
                    df_daily_display["Avg exposure %"] = df_daily_display[
                        "avg_exposure_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Realized %" not in df_daily_display.columns:
                    df_daily_display["Realized %"] = df_daily_display[
                        "realized_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Unrealized %" not in df_daily_display.columns:
                    df_daily_display["Unrealized %"] = df_daily_display[
                        "unrealized_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Total Return %" not in df_daily_display.columns:
                    df_daily_display["Total Return %"] = df_daily_display[
                        "total_return_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Drawdown %" not in df_daily_display.columns:
                    df_daily_display["Drawdown %"] = df_daily_display[
                        "drawdown_pct"
                    ].apply(lambda v: round(float(v), 2))

                # Rename drawdown_inr to Drawdown INR (this is the daily drop, not max)
                if (
                    "drawdown_inr" in df_daily_display.columns
                    and "Drawdown INR" not in df_daily_display.columns
                ):
                    df_daily_display = df_daily_display.rename(
                        columns={"drawdown_inr": "Drawdown INR"}
                    )

                # Select final column ordering (daily should have Drawdown, not Max drawdown)
                daily_cols = [
                    "Date",
                    "Equity",
                    "Avg exposure",
                    "Avg exposure %",
                    "Realized INR",
                    "Realized %",
                    "Unrealized INR",
                    "Unrealized %",
                    "Total Return INR",
                    "Total Return %",
                    "Drawdown INR",
                    "Drawdown %",
                ]
                daily_path = os.path.join(
                    run_dir, f"portfolio_daily_equity_curve_{label}.csv"
                )
                df_daily_display.to_csv(daily_path, index=False, columns=daily_cols)
                portfolio_csv_paths[f"daily_{label}"] = daily_path

                # Write monthly aggregated file: group daily display by Month (YYYY-MM) and aggregate
                try:
                    # Use df_daily_display which has Date column
                    monthly_num = df_daily_display.copy()
                    # Convert to period first, then apply on each element
                    monthly_num["Month"] = (
                        pd.to_datetime(monthly_num["Date"]).dt.to_period("M").apply(str)
                    )

                    # Define aggregation map
                    agg_map = {}
                    # Numeric columns that should be last value of the month
                    for col in [
                        "Equity",
                        "Avg exposure",
                        "Max drawdown INR",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "last"

                    # P&L columns should be summed since they're now incremental
                    for col in ["Realized INR", "Unrealized INR", "Total Return INR"]:
                        if col in monthly_num.columns:
                            agg_map[col] = "sum"

                    # Percent columns for P&L should be summed since they're incremental
                    for col in [
                        "Realized %",
                        "Unrealized %",
                        "Total Return %",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "sum"

                    # Other percent columns that should be last value of the month
                    for col in [
                        "Avg exposure %",
                        "Max drawdown %",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "last"

                    # Drawdown % should be max for the month
                    if "Drawdown %" in monthly_num.columns:
                        agg_map["Drawdown %"] = "max"
                    if "Drawdown INR" in monthly_num.columns:
                        agg_map["Drawdown INR"] = "max"

                    # sort by date so 'last' picks the end-of-month row
                    monthly_num = (
                        monthly_num.sort_values(by="Date")
                        .groupby("Month", as_index=False)
                        .agg(agg_map)
                    )

                    # Ensure the first monthly row is at initial capital
                    if not df_daily_display.empty and not monthly_num.empty:
                        first_day = df_daily_display.iloc[0]
                        if first_day["Equity"] == cfg.initial_capital:
                            first_month = str(
                                pd.to_datetime(first_day["Date"]).to_period("M")
                            )
                            # Check if first_month is already in monthly_num; if not, prepend it
                            if monthly_num.iloc[0]["Month"] != first_month:
                                # Create baseline first month row at initial capital
                                first_row_dict = {"Month": first_month}
                                for col in monthly_num.columns:
                                    if col == "Month":
                                        continue
                                    if col in ["Equity"]:
                                        first_row_dict[col] = int(cfg.initial_capital)
                                    elif col in ["Drawdown INR", "Drawdown %"]:
                                        first_row_dict[col] = 0
                                    else:
                                        first_row_dict[col] = 0.0 if "%" in col else 0

                                monthly_num = pd.concat(
                                    [pd.DataFrame([first_row_dict]), monthly_num],
                                    ignore_index=True,
                                )

                    # Format display version
                    monthly_disp = monthly_num.copy()

                    # Round Equity to integer
                    if "Equity" in monthly_disp.columns:
                        try:
                            monthly_disp["Equity"] = (
                                monthly_disp["Equity"]
                                .astype(float)
                                .round(0)
                                .astype(int)
                            )
                        except Exception:
                            pass

                    # Ensure INR columns are integers
                    for col in [
                        "Avg exposure",
                        "Realized INR",
                        "Unrealized INR",
                        "Total Return INR",
                        "Max drawdown INR",
                        "Drawdown INR",
                    ]:
                        if col in monthly_disp.columns:
                            try:
                                monthly_disp[col] = (
                                    pd.to_numeric(monthly_disp[col], errors="coerce")
                                    .fillna(0)
                                    .astype(int)
                                )
                            except Exception:
                                pass

                    # Ensure percent columns are float with 2 decimals
                    for col in [
                        "Avg exposure %",
                        "Realized %",
                        "Unrealized %",
                        "Total Return %",
                        "Max drawdown %",
                        "Drawdown %",
                    ]:
                        if col in monthly_disp.columns:
                            try:
                                monthly_disp[col] = (
                                    pd.to_numeric(monthly_disp[col], errors="coerce")
                                    .fillna(0.0)
                                    .apply(lambda v: round(float(v), 2))
                                )
                            except Exception:
                                pass

                    # Select final column ordering
                    monthly_cols = [
                        "Month",
                        "Equity",
                        "Avg exposure",
                        "Avg exposure %",
                        "Realized INR",
                        "Realized %",
                        "Unrealized INR",
                        "Unrealized %",
                        "Total Return INR",
                        "Total Return %",
                        "Max drawdown INR",
                        "Max drawdown %",
                    ]

                    # Only include columns that exist
                    monthly_cols = [
                        c for c in monthly_cols if c in monthly_disp.columns
                    ]

                    monthly_path = os.path.join(
                        run_dir, f"portfolio_monthly_equity_curve_{label}.csv"
                    )
                    monthly_disp.to_csv(monthly_path, index=False, columns=monthly_cols)
                    portfolio_csv_paths[f"monthly_{label}"] = monthly_path
                except Exception:
                    # non-fatal; continue
                    pass
            except Exception as e:
                print(f"DEBUG {label}: error in portfolio curve generation: {e}")
                import traceback

                traceback.print_exc()
                pass
        except Exception:
            # non-fatal; continue to next window
            pass

        # Legacy per-window params CSV block removed; we already create
        # `basket_{label}.csv` containing the parameter table and TOTAL row above.

    # Generate strategy results summary (comprehensive metrics per window)
    # First, collect portfolio curves, metrics, and trades for summary generation
    portfolio_curves_for_summary: dict[str, pd.DataFrame] = {}
    portfolio_metrics_for_summary: dict[str, pd.DataFrame] = {}
    trades_for_summary: dict[str, pd.DataFrame] = {}

    # Re-load the daily CSV files to get portfolio curves
    for label, daily_csv_path in portfolio_csv_paths.items():
        if label.startswith("daily_"):
            window_label = label.replace("daily_", "")
            try:
                port_df = pd.read_csv(daily_csv_path, parse_dates=["Date"])
                port_df.set_index("Date", inplace=True)
                portfolio_curves_for_summary[window_label] = port_df
            except Exception as e:
                print(f"Warning: could not load portfolio curve {daily_csv_path}: {e}")

    # Re-load the portfolio_key_metrics files from consolidated_csv_paths
    for label, metrics_csv_path in consolidated_csv_paths.items():
        if not label.startswith("trades_"):
            # These are the portfolio_key_metrics files
            try:
                metrics_df = pd.read_csv(metrics_csv_path)
                portfolio_metrics_for_summary[label] = metrics_df
            except Exception as e:
                print(f"Warning: could not load metrics {metrics_csv_path}: {e}")

    # Re-load the consolidated trades files
    # Match trades CSV files by window label (key format is "trades_1Y", "trades_3Y", etc.)
    for label, csv_path in consolidated_csv_paths.items():
        if label.startswith("trades_"):
            window_label = label.replace("trades_", "")
            try:
                trades_df = pd.read_csv(csv_path)
                trades_for_summary[window_label] = trades_df
            except Exception as e:
                print(f"Warning: could not load trades {csv_path}: {e}")

    # Generate and save strategy summary
    if portfolio_curves_for_summary and trades_for_summary:
        summary_path = _generate_strategy_summary(
            run_dir,
            portfolio_curves_for_summary,
            trades_for_summary,
            portfolio_metrics_for_summary,
            cfg.initial_capital,
        )
        if summary_path:
            print(f"Saved strategy summary: {summary_path}")

    # Generate comprehensive dashboard with all improvements
    print("\n📊 Generating hybrid financial dashboard...")
    try:
        from pathlib import Path

        from viz.hybrid_dashboard import HybridDashboard

        # Create hybrid dashboard instance
        dashboard = HybridDashboard(Path(run_dir))

        # Generate and save the dashboard
        dashboard_path = dashboard.save_dashboard(
            output_name="portfolio_dashboard",
            report_name=f"{strategy_name.title()} - {basket_name.title()} Basket",
        )

        print(f"✅ Dashboard saved: {dashboard_path}")
        print(f"🌐 Open in browser: file://{dashboard_path}")

    except Exception as e:
        import traceback

        print(f"⚠️ Dashboard generation failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        # Continue with rest of execution - dashboard failure shouldn't stop backtest

    save_summary(
        run_dir,
        {
            "runner": "run_basket",
            "strategy": strategy_name,
            "params_json": params_json,
            "interval": interval,
            "period": period,
            "bars_per_year": bars_per_year,
            "windows": [window_labels[w] for w in windows_years],
            "consolidated_csv": consolidated_csv_paths,
            "portfolio_curves_csv": portfolio_csv_paths,
            "portfolio_maxdd_by_window": window_maxdd,
            "symbols_bare": bare,
        },
    )

    print("\nSaved consolidated reports:")
    for k, v in consolidated_csv_paths.items():
        print(f"- {k}: {v}")
    print("Saved portfolio curves:")
    for k, v in portfolio_csv_paths.items():
        print(f"- {k}: {v}")

    # Generate visual plots for portfolio performance
    print("\n📊 Generating performance visualizations...")

    print("✅ Portfolio analysis complete!")


def run_basket_all_time(
    basket_file: str,
    strategy_name: str = "donchian",
    params_json: str = '{"length":20,"exit_option":1}',
    interval: str = "1d",
    use_cache_only: bool = False,
    cache_dir: str = "cache",
) -> None:
    """Full history, ALL window only."""
    return run_basket(
        basket_file=basket_file,
        strategy_name=strategy_name,
        params_json=params_json,
        interval=interval,
        period="max",
        windows_years=(None,),
        use_cache_only=use_cache_only,
        cache_dir=cache_dir,
    )


if __name__ == "__main__":
    from config import DEFAULT_BASKET_SIZE, get_available_baskets

    available_baskets = get_available_baskets()
    basket_info = ", ".join(
        [f"{size}({count})" for size, count in available_baskets.items()]
    )

    epilog = (
        f"Available baskets: {basket_info}\n"
        f"Default basket: {DEFAULT_BASKET_SIZE} (data/basket.txt)\n\n"
        "Examples:\n"
        "  # Use default basket (data/basket.txt):\n"
        "  python3 -m runners.run_basket --strategy ema_cross --params '{}' --interval 1d --period max\n\n"
        "  # Use specific basket size:\n"
        "  python3 -m runners.run_basket --basket_size large --strategy ema_cross --params '{}' --interval 1d --period max\n\n"
        "  # Use custom basket file:\n"
        "  python3 -m runners.run_basket --basket_file data/my_basket.txt --strategy ema_cross --params '{}' --interval 1d --period max\n"
    )

    ap = argparse.ArgumentParser(
        description="Run a basket of backtests and produce reports",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Basket selection (mutually exclusive)
    basket_group = ap.add_mutually_exclusive_group()
    basket_group.add_argument(
        "--basket_file",
        help="Path to custom basket file (txt with symbols, one per line)",
    )
    basket_group.add_argument(
        "--basket_size",
        choices=list(available_baskets.keys()),
        help=f"Predefined basket size. Available: {basket_info}",
    )
    ap.add_argument(
        "--strategy",
        default="ichimoku",  # Changed from donchian to ichimoku as primary strategy
        help="Strategy name in core.registry (e.g. ichimoku, donchian, ema_cross)",
    )
    ap.add_argument(
        "--params",
        default="{}",
        help='JSON string for strategy params, e.g. \'{"ema_fast":89,"ema_slow":144}\'. Empty {} uses strategy defaults.',
    )
    ap.add_argument("--interval", default="1d", help="Data interval, e.g. 1d or 60m")
    ap.add_argument(
        "--period",
        default="max",  # Changed from 5y to max for complete historical analysis
        help="Data history period for loader, e.g. 1y, 5y, max",
    )
    ap.add_argument(
        "--use_cache_only",
        action="store_true",
        default=True,  # Set to True by default to prevent interruptions from network issues
        help="Use only locally cached data (don't hit remote) if present",
    )
    ap.add_argument(
        "--cache_dir",
        default="data/cache",  # Updated to correct cache directory path
        help="Local cache directory for downloaded symbol data",
    )
    args = ap.parse_args()

    # Execute with comprehensive error handling and timeout management
    try:
        logger.info("Starting basket backtest execution...")
        logger.info(
            f"Configuration: strategy={args.strategy}, period={args.period}, cache_only={args.use_cache_only}"
        )

        start_time = time.time()

        # Use safe operation wrapper with timeout
        safe_operation(
            run_basket,
            basket_file=args.basket_file,
            basket_size=args.basket_size,
            strategy_name=args.strategy,
            params_json=args.params,
            interval=args.interval,
            period=args.period,
            use_cache_only=args.use_cache_only,
            cache_dir=args.cache_dir,
            timeout_seconds=TOTAL_TIMEOUT,
            operation_name="basket backtest",
        )

        execution_time = time.time() - start_time
        logger.info(
            f"✅ Basket backtest completed successfully in {execution_time:.1f}s"
        )

    except TimeoutError as e:
        logger.error(f"❌ Execution timed out: {e}")
        logger.error("Consider using --use_cache_only to avoid network delays")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("⚠️ Execution interrupted by user (Ctrl+C)")
        logger.info("Partial results may be available in the output directory")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Execution failed: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")

        # Provide helpful error resolution hints
        if "No module named" in str(e):
            logger.error("💡 Try: pip install -e . to install the package")
        elif "file not found" in str(e).lower() or "no such file" in str(e).lower():
            logger.error("💡 Check that the basket file and cache directory exist")
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            logger.error("💡 Try using --use_cache_only to avoid network issues")
        elif "memory" in str(e).lower():
            logger.error(
                "💡 Consider reducing basket size or using shorter time periods"
            )

        sys.exit(1)
