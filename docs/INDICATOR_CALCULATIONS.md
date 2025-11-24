# Consolidated Trades Indicator Calculations

This document explains how each indicator in the `consolidated_trades_*.csv` files is calculated and what values to expect.

## Overview
All indicators are calculated at **trade entry time** using data up to that point. They represent the market conditions when the trade was entered. Entry rows show empty values; exit rows show the calculated indicators.

**Total Indicators: 46**
- Regime Filters: 9
- Trend Strength: 6
- Momentum: 12
- Trend Structure: 13
- Volume: 4
- Kaufman Efficiency Ratio: 2

---

## 📊 REGIME FILTERS (9 Indicators)

### 1. India VIX
- **Source**: Dhan Historical Data (Security ID: 21)
- **Calculation**: VIX value classified into ranges
  ```python
  if vix < 12: "< 12"
  elif vix < 16: "12–16"
  elif vix < 20: "16–20"
  elif vix < 25: "20–25"
  else: ">25"
  ```
- **Expected Values**: `< 12`, `12–16`, `16–20`, `20–25`, `>25`
- **Interpretation**: Market volatility classification
  - `< 12`: Very low volatility (extreme calm)
  - `12–16`: Low volatility (normal calm)
  - `16–20`: Medium volatility (normal)
  - `20–25`: High volatility (nervous market)
  - `>25`: Extreme volatility (panic/uncertainty)

### 2-4. NIFTY200 > EMA (20, 50, 200)
- **Source**: NIFTY 200 index from Dhan (Security ID: 18)
- **Calculation**: 
  ```python
  nifty200_close > EMA(nifty200_close, period)
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**: Indicates if NIFTY200 is above its moving average
  - `True`: Bullish regime
  - `False`: Bearish regime

### 5-7. Trend Classification (Aroon 25, 50, 100)
- **Source**: NIFTY 200 price data
- **Calculation**: Uses Aroon indicator with **period-adaptive thresholds**
  ```python
  aroon_up, aroon_down = Aroon(high, low, period)
  
  # Adaptive thresholds based on period
  if period <= 25:      # Short-term: Strict (70/30)
      bull_threshold, neutral_gap = 70, 30
  elif period <= 50:    # Medium-term: Moderate (65/25)
      bull_threshold, neutral_gap = 65, 25
  else:                 # Long-term: Relaxed (60/20)
      bull_threshold, neutral_gap = 60, 20
  
  if aroon_up > bull_threshold and aroon_down < neutral_gap:
      return "Bull"
  elif aroon_down > bull_threshold and aroon_up < neutral_gap:
      return "Bear"
  else:
      return "Sideways"
  ```
- **Expected Values**: `Bull`, `Bear`, or `Sideways`
- **Periods**:
  - **Short-Trend (Aroon 25)**: 25-day trend (strict: 70/30)
  - **Medium-Trend (Aroon 50)**: 50-day trend (moderate: 65/25)
  - **Long-Trend (Aroon 100)**: 100-day trend (relaxed: 60/20)
- **Note**: Longer periods use relaxed thresholds to better capture bear markets

### 8-9. Volatility (14, 28)
- **Source**: Stock's ATR (Average True Range)
- **Calculation**: **Period-adaptive, India-calibrated thresholds**
  ```python
  atr = ATR(high, low, close, period)
  atr_pct = (atr / close) * 100
  
  # Adaptive thresholds based on period
  if period <= 14:      # Short-term: Higher (2.5/4.5)
      low_threshold, high_threshold = 2.5, 4.5
  elif period <= 21:    # Medium-term: Moderate (2.2/4.0)
      low_threshold, high_threshold = 2.2, 4.0
  else:                 # Long-term: Lower (2.0/3.5)
      low_threshold, high_threshold = 2.0, 3.5
  
  if atr_pct < low_threshold: "Low"
  elif atr_pct < high_threshold: "Med"
  else: "High"
  ```
- **Expected Values**: `Low`, `Med`, or `High`
- **Periods**:
  - **Volatility (14)**: 14-day ATR% (thresholds: 2.5%, 4.5%)
  - **Volatility (28)**: 28-day ATR% (thresholds: 2.0%, 3.5%)
- **Note**: Calibrated for Indian market volatility (higher than US markets). Longer periods use lower thresholds as they produce smoother values.

---

## 💪 TREND STRENGTH (6 Indicators)

### 1-2. ADX (14, 28)
- **Calculation**: Average Directional Index
  ```python
  adx_result = ADX(high, low, close, period)
  adx = adx_result['adx'][-1]
  ```
- **Expected Values**: Numeric (0-100, typically 0-60)
- **Interpretation** (Period-Adaptive):
  
  **ADX (14) - Short-term:**
  - < 20: Weak/no trend
  - 20-25: Emerging trend
  - 25-40: Strong trend
  - > 40: Very strong trend
  
  **ADX (28) - Long-term:**
  - < 15: Weak/no trend *(adjusted down)*
  - 15-20: Emerging trend *(adjusted down)*
  - 20-30: Strong trend *(adjusted down)*
  - > 30: Very strong trend *(adjusted down)*
  
- **Note**: Longer periods produce lower ADX values (~5 points lower for ADX(28) vs ADX(14)). Use period-appropriate thresholds when filtering.

### 3-4. DI_Bullish (14, 28)
- **Calculation**: Directional Indicator comparison
  ```python
  di_plus = adx_result['di_plus'][-1]
  di_minus = adx_result['di_minus'][-1]
  di_bullish = (di_plus > di_minus)
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: Buyers dominating (+DI > -DI)
  - `False`: Sellers dominating

### 5-6. Bull_Bear_Power (13;13, 26;26)
- **Calculation**: Elder's Bull/Bear Power
  ```python
  ema_13 = EMA(close, 13)
  bull_power = high - ema_13
  bear_power = low - ema_13
  bull_bear_power = bull_power + bear_power
  ```
- **Expected Values**: Numeric (can be positive or negative)
- **Interpretation**:
  - Positive: Bulls stronger
  - Negative: Bears stronger
  - Near 0: Balance

---

## 🚀 MOMENTUM (12 Indicators)

### 1-2. RSI (14, 28)
- **Calculation**: Relative Strength Index
  ```python
  rsi = RSI(close, period)
  ```
- **Expected Values**: Numeric (0-100)
- **Interpretation**:
  - < 30: Oversold
  - 30-70: Neutral
  - > 70: Overbought

### 3-4. MACD_Bullish (12;26;9, 24;52;18)
- **Calculation**: MACD crossover signal
  ```python
  macd = MACD(close, fast, slow, signal)
  macd_bullish = (macd['macd'][-1] > macd['signal'][-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: MACD line above signal (bullish)
  - `False`: MACD line below signal (bearish)

### 5-6. CCI (20, 40)
- **Calculation**: Commodity Channel Index
  ```python
  typical_price = (high + low + close) / 3
  cci = CCI(high, low, close, period)
  ```
- **Expected Values**: Numeric (typically -200 to +200)
- **Interpretation**:
  - < -100: Oversold
  - -100 to +100: Normal range
  - > +100: Overbought

### 7-8. Stoch_Bullish (14;3, 28;3)
- **Calculation**: Fast Stochastic crossover
  ```python
  stoch = Stochastic(high, low, close, k_period, d_period)
  stoch_bullish = (stoch['k'][-1] > stoch['d'][-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: %K above %D (bullish momentum)
  - `False`: %K below %D

### 9-10. Stoch_Slow_Bullish (5;3;3, 10;3;3)
- **Calculation**: Slow Stochastic crossover
  ```python
  stoch_slow = calculate_stochastic_slow(high, low, close, k, d, smooth)
  stoch_slow_bullish = (slow_k > slow_d)
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**: Similar to Fast Stochastic but smoother

### 11-12. StochRSI_Bullish (14;14, 28;28)
- **Calculation**: Stochastic RSI crossover
  ```python
  rsi = RSI(close, period)
  stoch_rsi = StochasticRSI(rsi, period)
  stoch_rsi_bullish = (stoch_rsi['k'][-1] > stoch_rsi['d'][-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**: Combines RSI with Stochastic for momentum

---

## 📈 TREND STRUCTURE (13 Indicators)

### 1-4. Price_Above_EMA (5, 20, 50, 200)
- **Calculation**:
  ```python
  ema = EMA(close, period)
  price_above_ema = (close[-1] > ema[-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: Price above EMA (bullish position)
  - `False`: Price below EMA (bearish position)

### 5-7. EMA Crossovers (5>20, 20>50, 50>200)
- **Calculation**:
  ```python
  ema_fast = EMA(close, fast_period)
  ema_slow = EMA(close, slow_period)
  ema_fast_above_slow = (ema_fast[-1] > ema_slow[-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: Fast EMA above slow (bullish alignment)
  - `False`: Fast EMA below slow (bearish alignment)

### 8-9. Price_Above_Kijun (26, 52)
- **Calculation**: Ichimoku Kijun-sen (Base Line)
  ```python
  kijun = (highest_high(period) + lowest_low(period)) / 2
  price_above_kijun = (close[-1] > kijun[-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: Price above baseline (bullish)
  - `False`: Price below baseline

### 10-11. Tenkan_Above_Kijun (9; 26, 18; 52)
- **Calculation**: Ichimoku Tenkan-sen vs Kijun-sen
  ```python
  tenkan = (highest_high(9) + lowest_low(9)) / 2
  kijun = (highest_high(26) + lowest_low(26)) / 2
  tenkan_above_kijun = (tenkan[-1] > kijun[-1])
  ```
- **Expected Values**: `True` or `False`
- **Interpretation**:
  - `True`: Tenkan-sen cross above (bullish signal)
  - `False`: Below (bearish)

### 12-13. Bollinger_Band_Position (20;2, 40;2)
- **Calculation**: Price position relative to Bollinger Bands
  ```python
  middle = SMA(close, period)
  std_dev = STDEV(close, period)
  upper = middle + (std_dev * 2)
  lower = middle - (std_dev * 2)
  
  if price > upper: "Above"
  elif price < lower: "Below"
  else: "Middle"
  ```
- **Expected Values**: `Above`, `Middle`, or `Below`
- **Interpretation**:
  - `Above`: Potentially overbought
  - `Middle`: Normal range
  - `Below`: Potentially oversold

---

## 📊 VOLUME (4 Indicators)

### 1-2. MFI (20, 40)
- **Calculation**: Money Flow Index
  ```python
  typical_price = (high + low + close) / 3
  raw_money_flow = typical_price * volume
  
  positive_flow = sum(raw_money_flow where price_up)
  negative_flow = sum(raw_money_flow where price_down)
  money_ratio = positive_flow / negative_flow
  mfi = 100 - (100 / (1 + money_ratio))
  ```
- **Expected Values**: Numeric (0-100)
- **Interpretation**:
  - < 20: Oversold
  - 20-80: Normal
  - > 80: Overbought

### 3-4. CMF (20, 40)
- **Calculation**: Chaikin Money Flow
  ```python
  clv = ((close - low) - (high - close)) / (high - low)
  money_flow_volume = clv * volume
  cmf = sum(money_flow_volume, period) / sum(volume, period)
  ```
- **Expected Values**: Numeric (-1.0 to +1.0, typically -0.5 to +0.5, rounded to 2 decimals)
- **Interpretation**:
  - > 0: Buying pressure
  - < 0: Selling pressure
  - Near 0: Balanced

---

## 🎯 KAUFMAN EFFICIENCY RATIO (2 Indicators)

### 1-2. KER (10, 30)
- **Calculation**: Kaufman Efficiency Ratio
  ```python
  direction = abs(close[t] - close[t-n])
  volatility = sum(abs(close[i] - close[i-1]) for i in range(t-n+1, t+1))
  ker = direction / volatility
  ```
- **Expected Values**: Numeric (0.0 to 1.0, rounded to 3 decimals)
- **Interpretation**:
  - < 0.3: High noise (choppy/mean-reverting market)
  - 0.3-0.7: Moderate trend
  - > 0.7: Low noise (strong trending market)
  - 1.0: Perfect trend (price moves in one direction only)
- **Usage**: Helps identify if the market is trending or ranging
  - High KER (>0.7): Follow trend indicators
  - Low KER (<0.3): Avoid trend-following strategies

---

## 🔍 Data Flow & Verification

### Calculation Process:
1. **Entry Time**: All indicators calculated using data up to trade entry
2. **Data Source**: Stock's OHLCV data from `symbol_results[symbol]['data']`
3. **Market Data**: India VIX and NIFTY200 loaded separately and aligned
4. **Function**: `_calculate_all_indicators_for_consolidated(entry_data)`
5. **Output**: Dictionary with all 44 indicators

### File Location:
```
reports/
└── <timestamp>-<strategy>-<basket>-<interval>/
    ├── consolidated_trades_1Y.csv    # 1-year window
    ├── consolidated_trades_3Y.csv    # 3-year window
    ├── consolidated_trades_5Y.csv    # 5-year window
    └── consolidated_trades_MAX.csv   # Full history
```

### Row Structure:
Each trade has 2 rows:
1. **Exit Row**: Trade #, Symbol, "Exit long", Date, Price, P&L, **ALL INDICATORS POPULATED**
2. **Entry Row**: Trade #, Symbol, "Entry long", Date, Price, **ALL INDICATORS EMPTY**

### Sample Verification:
```bash
# Check headers
head -1 consolidated_trades_1Y.csv | tr ',' '\n' | nl

# Check exit row (line 2) indicators
head -2 consolidated_trades_1Y.csv | tail -1 | cut -d',' -f22-67

# Count total indicators
head -1 consolidated_trades_1Y.csv | tr ',' '\n' | tail -46 | wc -l
# Should output: 46
```

---

## 📝 Notes

1. **Empty Values**: Entry rows have empty indicator values by design
2. **Boolean Values**: `True`/`False` stored as strings in CSV
3. **Numeric Precision**: 
   - ADX, RSI, CCI, MFI, CMF: 2 decimal places
   - Bull_Bear_Power: 2 decimal places
   - KER: 3 decimal places
4. **Categorical Values**: 
   - Trend: `Bull`, `Bear`, `Sideways`
   - Volatility: `Low`, `Med`, `High`
   - BB Position: `Above`, `Middle`, `Below`
   - VIX Range: `< 12`, `12–16`, `16–20`, `20–25`, `>25`

5. **Data Alignment**: India VIX and NIFTY200 are forward-filled to align with stock dates

6. **VIX Ranges**: India VIX shown as ranges (< 12, 12–16, 16–20, 20–25, >25) instead of absolute values

7. **Historical Note**: Old indicators (SMAs, HMA, VWMA, Williams %R, Momentum, Ultimate Oscillator, Aroon Up/Down/Osc) were removed to focus on essential trading signals.
