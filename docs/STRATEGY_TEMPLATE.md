# Strategy Documentation Template

Use this template when creating new strategies or updating existing strategy documentation.

## Module Docstring Template

```python
"""
Strategy Name
=============

**Type**: Trend Following / Mean Reversion / Momentum / Hybrid

**Summary**: One-line description of what the strategy does.

Entry Conditions:
-----------------
1. Primary signal (indicator/pattern details)
2. Filter 1 (confirmation condition)
3. Filter 2 (if applicable)

Exit Conditions:
----------------
1. Signal reversal
2. Take profit at X%
3. Stop loss at X% (or ATR-based: N × ATR)

Filters:
--------
- VIX Filter: Trade when VIX < X OR VIX > Y
- ATR% Filter: ATR(14)% > X%
- ADX Filter: ADX(28) > X (trend strength)
- Weekly Filter: [describe if applicable]

Pyramiding:
-----------
- Max Levels: N
- Pyramid Condition: [describe when to add]

Parameters:
-----------
- param1 (int): Description. Default: X
- param2 (float): Description. Default: Y.Y
- use_filter (bool): Description. Default: True

Performance Notes:
------------------
- Best timeframe: 1d / 125m / 75m
- Typical win rate: X%
- Suitable markets: [trending/volatile/ranging]

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.

References:
-----------
- Original source (if adapted from TradingView/Pine Script)
- Related strategies in the codebase
"""
```

## Class Docstring Template

```python
class StrategyName(Strategy):
    """
    Brief one-line description.

    Entry: Primary entry condition summary
    Exit: Primary exit condition summary
    
    Risk Management:
    - Stop Loss: Description
    - Take Profit: Description
    - Position Sizing: Description
    """
```

## Parameter Documentation

Always document class-level parameters with inline comments:

```python
class ExampleStrategy(Strategy):
    # ===== INDICATOR PARAMETERS =====
    fast_period = 25        # Fast MA period
    slow_period = 100       # Slow MA period
    
    # ===== ENTRY FILTERS =====
    use_vix_filter = True   # VIX < 13 OR VIX > 19
    vix_low = 13.0          # Trade when VIX below this
    vix_high = 19.0         # Trade when VIX above this
    
    use_atr_filter = True   # ATR% > threshold
    atr_pct_min = 3.0       # Minimum ATR% for entry
    
    # ===== RISK MANAGEMENT =====
    use_stop_loss = True    # Enable ATR-based stop
    atr_multiplier = 2.0    # Stop at N × ATR below entry
    
    # ===== PYRAMIDING =====
    max_pyramid = 3         # Maximum pyramid levels
    pyramid_on_dip = True   # Add on RSI dips
```

## Method Documentation

```python
def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
    """Setup data and initialize indicators.
    
    This method is called once at the start of backtesting.
    Use self.I() to register indicators for proper memoization.
    """
    ...

def should_enter(self, i: int) -> bool:
    """Determine if entry conditions are met at bar i.
    
    Args:
        i: Current bar index (uses i-1 data to avoid lookahead)
        
    Returns:
        True if all entry conditions are satisfied
    """
    ...

def should_exit(self, i: int) -> bool:
    """Determine if exit conditions are met at bar i.
    
    Args:
        i: Current bar index (uses i-1 data to avoid lookahead)
        
    Returns:
        True if any exit condition is triggered
    """
    ...
```

## Example: Well-Documented Strategy

```python
"""
TEMA-LSMA Crossover Strategy
============================

**Type**: Trend Following

**Summary**: Uses TEMA/LSMA crossover for trend detection with ATR% and ADX filters.

Entry Conditions:
-----------------
1. TEMA(25) crosses above LSMA(100) (bullish crossover)
2. ATR(14)% > 3.5% (volatility filter - ensure sufficient movement)
3. ADX(28) > 25 (trend strength filter - confirm trending market)

Exit Conditions:
----------------
1. Bearish crossunder (TEMA crosses below LSMA)
2. ATR-based stop loss at entry - N × ATR(14) [optional]

Filters:
--------
- ATR% Filter: Ensures minimum volatility for profitable moves
- ADX Filter: Avoids ranging markets where crossovers whipsaw

Parameters:
-----------
- fast_length (int): TEMA period. Default: 25
- slow_length (int): LSMA period. Default: 100
- atr_14_min (float): Minimum ATR%. Default: 3.5
- adx_28_min (float): Minimum ADX. Default: 25

Performance Notes:
------------------
- Best on daily timeframe for swing trades
- Win rate improves with ADX filter but reduces trade frequency
- TEMA responds faster than traditional EMAs, reducing lag

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""


class TemaLsmaCrossover(Strategy):
    """TEMA-LSMA Crossover with ATR% and ADX filters.
    
    Entry: TEMA > LSMA with volatility and trend confirmation
    Exit: Bearish crossunder or ATR stop
    """
    
    # ===== MA PARAMETERS =====
    fast_length = 25    # TEMA period (fast, responsive)
    slow_length = 100   # LSMA period (slow, smooth)
    
    # ===== ENTRY FILTERS =====
    atr_14_min = 3.5    # ATR(14)% > 3.5% (volatility)
    adx_28_min = 25.0   # ADX(28) > 25 (trend strength)
    
    # ===== RISK MANAGEMENT =====
    use_atr_stop = False        # ATR-based stop loss
    atr_stop_multiplier = 5.0   # Stop at entry - N × ATR(14)
```

---

## Checklist for New Strategies

- [ ] Module docstring with all sections
- [ ] Class docstring with entry/exit summary
- [ ] Parameter comments (inline)
- [ ] Method docstrings for prepare/should_enter/should_exit
- [ ] No lookahead bias (use i-1 for decisions)
- [ ] Proper indicator registration with self.I()
- [ ] Filter toggles (use_xxx_filter) for flexibility
- [ ] Risk management parameters documented

---

*Template version: 1.0 | Last updated: January 7, 2026*
