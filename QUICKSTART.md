# Quick Start: Run Ichimoku Backtests

This guide helps you run Ichimoku strategy backtests on 6 market segments in under 5 minutes.

## TL;DR - Just Run This

```bash
./run_ichimoku_backtests.sh
```

That's it! The script will run all 6 backtests sequentially and generate reports.

## What This Does

Runs Ichimoku backtests on:
1. LargeCap LowBeta (38 stocks)
2. LargeCap HighBeta (60 stocks)
3. MidCap LowBeta (134 stocks)
4. MidCap HighBeta (98 stocks)
5. SmallCap LowBeta (135 stocks)
6. SmallCap HighBeta (107 stocks)

**Total**: 572 stocks analyzed

## Before You Start

### Check Dependencies (probably already installed)

```bash
python -c "import pandas, numpy, scipy, yfinance; print('✅ Ready to run')"
```

If you get an error:
```bash
conda install -y yfinance scipy
```

## Running the Backtests

### Option 1: All at Once (Recommended)
```bash
./run_ichimoku_backtests.sh
```

Expected time: 1.5-2 hours

### Option 2: One at a Time

```bash
# Just LargeCap LowBeta
conda run python -m runners.run_basket \
    --basket_file data/basket_largecap_lowbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max
```

## Viewing Results

After completion, check the `reports/` directory:

```bash
ls -lh reports/
```

Each backtest creates a folder with:
- 📊 CSV files with metrics
- 📈 Equity curves
- 📉 Trade logs
- 🌐 Interactive dashboard (`quantlab_dashboard.html`)

## Understanding the Output

### Key Files to Review

1. **`strategy_backtests_summary.csv`**
   - Quick overview of all time periods
   - Returns, Sharpe ratio, win rate, etc.

2. **`portfolio_daily_equity_curve_MAX.csv`**
   - Daily portfolio values
   - Use for charting performance

3. **`consolidated_trades_MAX.csv`**
   - Every trade with entry/exit
   - P&L, drawdown, indicators

4. **`quantlab_dashboard.html`**
   - Visual charts and graphs
   - Open in browser

### What to Look For

✅ **Good Signs**:
- Positive CAGR
- Sharpe Ratio > 1
- Win Rate > 50%
- Max Drawdown < 30%
- Profit Factor > 1.5

⚠️ **Warning Signs**:
- Negative returns
- High drawdowns
- Very low trade count
- Profit factor < 1

## Troubleshooting

### "No data available for {SYMBOL}"
Network issue. The script will continue with other symbols.

### "No module named yfinance"
```bash
conda install -y yfinance
```

### Script stops midway
Check the error message. Usually a network or data issue. Re-run the script - it will skip already completed backtests.

### Dashboard shows "No module named plotly"
Install plotly (optional):
```bash
conda install -y plotly
```

## What Next?

After running backtests:
1. Compare returns across segments
2. Find best risk-adjusted returns (Sharpe ratio)
3. Analyze which market cap/beta performs best
4. Consider parameter optimization
5. Try other strategies

## Need More Details?

See comprehensive guides:
- **`RUN_ICHIMOKU_BACKTESTS.md`**: Complete usage guide (400+ lines)
- **`IMPLEMENTATION_SUMMARY.md`**: Technical details
- **`strategies/ichimoku.py`**: Strategy implementation

## Quick Reference

### Ichimoku Parameters (Default)
```
Conversion: 9
Base: 26
Lagging: 52
```

### Market Segments
| Segment | Stocks | File |
|---------|--------|------|
| LargeCap LowBeta | 38 | `basket_largecap_lowbeta.txt` |
| LargeCap HighBeta | 60 | `basket_largecap_highbeta.txt` |
| MidCap LowBeta | 134 | `basket_midcap_lowbeta.txt` |
| MidCap HighBeta | 98 | `basket_midcap_highbeta.txt` |
| SmallCap LowBeta | 135 | `basket_smallcap_lowbeta.txt` |
| SmallCap HighBeta | 107 | `basket_smallcap_highbeta.txt` |

### Time Windows Analyzed
- 1Y (last 1 year)
- 3Y (last 3 years)
- 5Y (last 5 years)
- MAX (all available history)

## Support

Questions? Check:
1. Error messages in terminal
2. `summary.json` in report folders
3. Full documentation in `RUN_ICHIMOKU_BACKTESTS.md`

---

**Ready?** Just run: `./run_ichimoku_backtests.sh`
