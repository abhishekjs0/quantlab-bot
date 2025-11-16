# Backtest Results - Quick Reference

After running `python3 -m runners.run_basket ...`, backtest results are saved here.

## 📊 Quick Access - Latest Results

After each backtest run, a `LATEST` folder is created in the format:
```
reports/MMDD-HHMM-LATEST-<strategy>-<basket>-<interval>/
├── LATEST_BACKTEST_METRICS.csv
```

**To view the latest metrics:**

```bash
# View the latest metrics file directly
cat reports/*LATEST*/LATEST_BACKTEST_METRICS.csv
```

Or navigate to the latest folder and open the CSV file.

## 📁 Full Report Structure

Each complete backtest report directory (e.g., `1115-1011-kama-crossover-basket-test-1d/`) contains all details:

### Metrics Files
- `portfolio_key_metrics_1Y.csv` - Portfolio metrics for 1Y window
- `portfolio_key_metrics_3Y.csv` - Portfolio metrics for 3Y window
- `portfolio_key_metrics_5Y.csv` - Portfolio metrics for 5Y window
- `portfolio_key_metrics_MAX.csv` - Portfolio metrics for full historical data
- `strategy_backtests_summary.csv` - Per-symbol backtest summary

### Trade Files
- `consolidated_trades_1Y.csv` - Individual trades for 1Y window
- `consolidated_trades_3Y.csv` - Individual trades for 3Y window
- `consolidated_trades_5Y.csv` - Individual trades for 5Y window
- `consolidated_trades_MAX.csv` - Individual trades for full period

### Equity Curves
- `portfolio_daily_equity_curve_*.csv` - Daily portfolio equity curves
- `portfolio_monthly_equity_curve_*.csv` - Monthly portfolio equity curves

### Dashboard
- `quantlab_dashboard.html` - Interactive dashboard (open in browser)

## 📈 Metrics Explained

| Metric | Meaning |
|--------|---------|
| **Net P&L %** | Total profit/loss as percentage of initial capital |
| **Total Trades** | Number of trades generated in the period |
| **Win Rate %** | Percentage of profitable trades |
| **Profit Factor** | Ratio of gains to losses (>1.0 = profitable) |
| **Max Drawdown %** | Largest peak-to-trough decline |
| **IRR %** | Internal Rate of Return (accounting for deployment) |
| **CAGR %** | Compound Annual Growth Rate |
| **Avg P&L/Trade %** | Average profit per trade as percentage |
| **Avg Bars/Trade** | Average bars/days held per trade |

## 🔍 Example: Quick Check of Latest Results

```bash
# Check latest metrics in one command
head -5 reports/*LATEST*/LATEST_BACKTEST_METRICS.csv
```

## 💡 Tips

1. **Always check latest folder first**: Results auto-update after each `run_basket` execution
2. **Compare windows**: Check 1Y, 3Y, 5Y to see performance consistency
3. **Check profit factor**: >1.0 = profitable strategy
4. **Monitor drawdown**: Larger drawdowns mean more volatility and risk
5. **Dashboard**: Open the HTML file in browser for interactive visualization

