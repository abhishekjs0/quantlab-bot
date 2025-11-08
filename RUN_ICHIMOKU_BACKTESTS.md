# Running Ichimoku Backtests on Market Segments

## Overview

This guide explains how to run Ichimoku strategy backtests on 6 different market segments (largecap/midcap/smallcap × lowbeta/highbeta) sequentially.

## Prerequisites

### 1. Install Required Dependencies

```bash
pip install pandas numpy scipy yfinance
```

**Note**: If you encounter network timeouts with PyPI, try:
```bash
pip install --retries 10 --timeout 120 pandas numpy scipy yfinance
```

Or use a mirror:
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas numpy scipy yfinance
```

### 2. Verify Installation

```bash
python -c "import pandas, numpy, scipy, yfinance; print('✓ All dependencies installed')"
```

## Market Segments

The backtests will run on these 6 basket files:

1. **LargeCap LowBeta** (38 symbols)
   - File: `data/basket_largecap_lowbeta.txt`
   - Description: Large cap stocks with low market beta

2. **LargeCap HighBeta** (60 symbols)
   - File: `data/basket_largecap_highbeta.txt`
   - Description: Large cap stocks with high market beta

3. **MidCap LowBeta** (134 symbols)
   - File: `data/basket_midcap_lowbeta.txt`
   - Description: Mid cap stocks with low market beta

4. **MidCap HighBeta** (98 symbols)
   - File: `data/basket_midcap_highbeta.txt`
   - Description: Mid cap stocks with high market beta

5. **SmallCap LowBeta** (135 symbols)
   - File: `data/basket_smallcap_lowbeta.txt`
   - Description: Small cap stocks with low market beta

6. **SmallCap HighBeta** (107 symbols)
   - File: `data/basket_smallcap_highbeta.txt`
   - Description: Small cap stocks with high market beta

**Total**: 572 unique symbols across all segments

## Running the Backtests

### Option 1: Automated Sequential Execution (Recommended)

Run all 6 backtests sequentially using the provided script:

```bash
./run_ichimoku_backtests.sh
```

This script will:
- Run each backtest one at a time
- Fetch historical data from Yahoo Finance (yfinance) if not cached
- Cache the data locally in `data/cache/` for future use
- Generate comprehensive reports in `reports/` directory
- Show progress after each completed backtest
- Stop on error to prevent incomplete runs

**Expected Runtime**: 15-30 minutes per segment (depends on network speed and data volume)

### Option 2: Manual Execution

Run individual backtests manually:

#### 1. LargeCap LowBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_largecap_lowbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

#### 2. LargeCap HighBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_largecap_highbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

#### 3. MidCap LowBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_midcap_lowbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

#### 4. MidCap HighBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_midcap_highbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

#### 5. SmallCap LowBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_smallcap_lowbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

#### 6. SmallCap HighBeta
```bash
python -m runners.run_basket \
    --basket_file data/basket_smallcap_highbeta.txt \
    --strategy ichimoku \
    --interval 1d \
    --period max \
    --params '{}'
```

## Data Fetching

### How Data is Loaded

The system uses a multi-tier data loading strategy:

1. **Cached Data (Fastest)**: Checks `data/cache/` for existing OHLCV data
2. **YFinance Fallback**: If cache is missing, fetches from Yahoo Finance automatically
3. **Auto-Caching**: Downloaded data is automatically saved to cache for future use

### Cache Location

- **Directory**: `data/cache/`
- **Format**: CSV files named `yfinance_{SYMBOL}.csv`
- **Retention**: Permanent (until manually deleted)

### Troubleshooting Data Issues

If data fetching fails:

1. **Check Internet Connection**: Ensure you can access finance.yahoo.com
2. **Verify Symbol Names**: Ensure basket files contain valid NSE symbols
3. **Manual Cache**: Pre-download data and place in `data/cache/yfinance_{SYMBOL}.csv`
4. **Use Cached Mode**: If you have existing cache, enable `--use_cache_only` flag

## Ichimoku Strategy Parameters

The backtests use default Ichimoku parameters:

```python
{
    "conversion_length": 9,    # Tenkan-sen (Conversion Line)
    "base_length": 26,         # Kijun-sen (Base Line)  
    "lagging_length": 52,      # Senkou Span B (Leading Span B)
}
```

### Signal Generation

- **Entry**: Conversion line crosses above base line AND price is above cloud
- **Exit**: Base line crosses above conversion line AND price is below cloud
- **Filters**: All filters disabled for baseline performance

## Output Reports

Each backtest generates comprehensive reports in `reports/{TIMESTAMP}-ichimoku-{BASKET}-1d/`:

### Generated Files

1. **Portfolio Metrics**
   - `portfolio_key_metrics_{WINDOW}.csv` - Performance metrics (1Y, 3Y, 5Y, MAX)
   - `strategy_backtests_summary.csv` - Consolidated multi-window summary

2. **Equity Curves**
   - `portfolio_daily_equity_curve_{WINDOW}.csv` - Daily portfolio values
   - `portfolio_monthly_equity_curve_{WINDOW}.csv` - Monthly aggregated values

3. **Trade Logs**
   - `consolidated_trades_{WINDOW}.csv` - Detailed trade-by-trade analysis
   - Includes: Entry/Exit times, P&L, Drawdown, Indicators, Risk metrics

4. **Visualizations**
   - `quantlab_dashboard.html` - Interactive HTML dashboard with charts

### Key Metrics Reported

- **Returns**: Net P&L %, CAGR, Total Return
- **Risk**: Max Drawdown, Volatility, VaR, Sharpe/Sortino/Calmar Ratios
- **Trading**: Win Rate, Profit Factor, Average Trade, Trade Duration
- **Alpha**: IRR, Alpha, Beta relative to Nifty 50 benchmark

## Validation

### Success Criteria

A successful backtest should:
- ✅ Complete without errors
- ✅ Generate all CSV files and dashboard
- ✅ Have trades > 0 (strategy found signals)
- ✅ Have Max Drawdown < 100% (no total loss)
- ✅ Have positive Profit Factor

### Review Checklist

After running backtests, verify:

1. [ ] All 6 backtests completed
2. [ ] Reports directory contains 6 timestamped folders
3. [ ] Each folder has dashboard.html and CSV files
4. [ ] No error messages in terminal output
5. [ ] Metrics appear reasonable (no extreme outliers)

## Advanced Options

### Using Cached Data Only

If you have pre-fetched data:

```bash
python -m runners.run_basket \
    --basket_file data/basket_largecap_lowbeta.txt \
    --strategy ichimoku \
    --use_cache_only
```

### Custom Time Period

For faster testing with shorter history:

```bash
python -m runners.run_basket \
    --basket_file data/basket_test.txt \
    --strategy ichimoku \
    --period 1y    # Options: 1y, 2y, 5y, max
```

### Custom Parameters

Override default Ichimoku parameters:

```bash
python -m runners.run_basket \
    --basket_file data/basket_largecap_lowbeta.txt \
    --strategy ichimoku \
    --params '{"conversion_length":7,"base_length":22,"lagging_length":44}'
```

## Monitoring Progress

The script provides real-time progress updates:

```
========================================
Starting: 1. LargeCap LowBeta
Basket: data/basket_largecap_lowbeta.txt
Progress: 0/6 completed
========================================

Fetching data for RELIANCE using yfinance...
✓ Fetched and cached RELIANCE
Fetching data for INFY using yfinance...
✓ Fetched and cached INFY
...

✅ Completed: 1. LargeCap LowBeta
Progress: 1/6 completed
```

## Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError: No module named 'yfinance'"
```bash
pip install yfinance
```

#### 2. "Cache missing for {SYMBOL}"
- Ensure `--use_cache_only` is NOT set (default is False)
- Check internet connection
- Verify symbol is valid NSE ticker

#### 3. "No trades generated"
- Strategy found no signals (normal for some periods/stocks)
- Try different time period or parameters
- Check if data quality is good

#### 4. Network timeout during data fetch
- Increase timeout: Add `--cache_dir` flag
- Pre-download data manually
- Use cached data if available

### Getting Help

For issues or questions:
1. Check logs in reports directory
2. Review `summary.json` in each report folder
3. Verify data files in `data/cache/`
4. Open GitHub issue with error details

## Performance Expectations

### Runtime Estimates

- **LargeCap LowBeta** (38 symbols): ~5-10 minutes
- **LargeCap HighBeta** (60 symbols): ~8-15 minutes
- **MidCap LowBeta** (134 symbols): ~15-25 minutes
- **MidCap HighBeta** (98 symbols): ~12-20 minutes
- **SmallCap LowBeta** (135 symbols): ~15-25 minutes
- **SmallCap HighBeta** (107 symbols): ~12-20 minutes

**Total Sequential Runtime**: ~1.5-2 hours

### Disk Space

- **Data Cache**: ~50-100 MB per segment
- **Reports**: ~5-10 MB per segment
- **Total**: ~350-650 MB for all 6 segments

## Next Steps

After successful backtests:

1. Review dashboards in each report folder
2. Compare performance across market segments
3. Analyze which segments perform best with Ichimoku
4. Consider optimizing parameters for specific segments
5. Backtest additional strategies for comparison

## References

- **Ichimoku Strategy**: `strategies/ichimoku.py`
- **Runner Script**: `runners/run_basket.py`
- **Data Loader**: `data/loaders.py`
- **Basket Script**: `run_ichimoku_backtests.sh`
