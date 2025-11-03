# on_bar() Execution Model in QuantLab

## Overview

The QuantLab backtesting engine uses a **bar-by-bar execution model** where trading decisions are made on the current bar and executed on the next bar's open. This is the industry standard for realistic backtesting.

---

## Key Differences: `on_bar()` vs `next()`

### `on_bar()` - QuantLab Standard
**Current Implementation in QuantLab**

```python
def on_bar(self, ts, row, state: dict[str, Any]) -> dict[str, Any]:
    """
    Process each bar/candle of data.
    
    Args:
        ts: Timestamp of current bar (when signal is generated)
        row: Current bar data (OHLCV)
        state: Current strategy state (qty, cash, equity)
    
    Returns:
        Dictionary with trading signals: {"enter_long": bool, "exit_long": bool}
    """
    return {"enter_long": False, "exit_long": False}
```

**Characteristics:**
- ✅ Called once per bar/candle
- ✅ Receives CURRENT bar data (OHLCV)
- ✅ Returns signals as dict (not boolean)
- ✅ No direct position management (handled by engine)
- ✅ Uses previous bar data to prevent future leak
- ✅ **SIGNAL GENERATED**: Current bar close
- ✅ **EXECUTION**: Next bar open

### `next()` - Backtesting.py Standard
**Not used in QuantLab (for reference only)**

```python
def next(self):
    """
    Legacy method from backtesting.py framework.
    
    Characteristics:
    - Called once per bar
    - Manages positions directly (self.buy(), self.sell())
    - May allow same-bar execution (lookahead)
    - Tightly coupled to backtesting.py internals
    """
    pass
```

---

## Execution Flow Diagram

### Timeline of a Trade

```
BAR 1 (i=0): High=100, Low=98, Close=99
  └─> on_bar() called with row=Bar1
  └─> Analyzes: price, indicators, previous bars
  └─> Returns: {"enter_long": False, ...}
  └─> No execution

BAR 2 (i=1): High=102, Low=99, Close=101
  └─> on_bar() called with row=Bar2
  └─> Signal detected: {"enter_long": True, ...}
  └─> Returns: enter_long=True
  └─> **SIGNAL GENERATED AT BAR2 CLOSE**

BAR 3 (i=2): High=103, Low=100, Open=102, Close=102.5
  └─> Entry executed at Bar3 Open = 102 ✅
  └─> Position entry_price = 102
  └─> Tracking starts: qty, stop, etc.

BAR 4 (i=3): ...
  └─> on_bar() checks for exit signals
  └─> If exit signal: {"exit_long": True}
  └─> Exit executed at Bar4 Open
```

---

## Core Execution Logic (engine.py)

### Step 1: Signal Generation (Current Bar)
```python
# Line 56-58 in core/engine.py
# Signals are determined on current bar
state = {"qty": qty, "cash": cash, "equity": equity}
act: dict[str, Any] = self.strategy.on_bar(ts, row, state)
```

**Context:**
- `ts`: Timestamp of current bar
- `row`: OHLCV data of current bar
- Strategy analyzes: close, indicators, previous bars
- **NO FUTURE DATA LEAKED** (only current+past data used)

### Step 2: Execution (Next Bar Open)
```python
# Line 65 in core/engine.py
# Exits and entries are executed at NEXT BAR's open

if self.cfg.execute_on_next_open:
    if i + 1 < len(data):  # Ensure next bar exists
        next_row = data.iloc[i + 1]
        next_open = float(next_row["open"])
        
        # Execute entry or exit at next_open price
```

**Mechanics:**
- Uses `next_open` price (not current bar's close)
- Prevents lookahead bias
- Realistic market execution simulation

---

## Why on_bar() Design is Better

### 1. **No Future Leak** ✅
```python
# on_bar() implementation - SAFE
def on_bar(self, ts, row, state):
    idx = self.data.index.get_loc(ts)
    
    # Use ONLY current and PREVIOUS bars
    close_now = row.close               # Current bar close
    close_prev = self.data.close.iloc[idx - 1]  # Previous bar
    
    # NEVER access self.data[idx+1] (next bar) - would be lookahead!
    return {"enter_long": close_now > close_prev}
```

### 2. **Clean Signal/Execution Separation** ✅
```python
# on_bar() returns signals only
return {
    "enter_long": True,           # Signal (not execution)
    "exit_long": False,
    "stop": 99.50,               # Optional: stop price
}

# Engine handles execution details
# (fills, position sizing, equity tracking, etc.)
```

### 3. **Realistic Market Simulation** ✅
```
Signal: Generated at close of Bar N
Execution: At open of Bar N+1
Result: Realistic market fill (between open and close)
```

### 4. **State Management** ✅
```python
# on_bar() receives current state
def on_bar(self, ts, row, state):
    qty = state["qty"]                  # Current position size
    cash = state["cash"]                # Available cash
    equity = state["equity"]            # Total account equity
    
    # Make decisions based on current state
    if qty == 0:  # No position
        return {"enter_long": True}
    else:  # Already in position
        return {"exit_long": True}
```

---

## Practical Example: Envelope+KD Strategy

### How It Prevents Lookahead

```python
def on_bar(self, ts, row, state):
    """Signal generation on current bar, exec on next bar open."""
    
    # Get current bar index
    idx = self.data.index.get_loc(ts)
    
    # MIN_BARS check: Need sufficient historical data
    if idx < min_bars:
        return {"enter_long": False, "exit_long": False}
    
    # Current bar values
    close_now = row.close                      # Bar N close
    basis_now = self.envelope_basis[idx]       # Bar N indicator value
    
    # Previous bar values (lookback)
    close_prev = self.data.close.iloc[idx - 1]  # Bar N-1 close
    basis_prev = self.envelope_basis[idx - 1]   # Bar N-1 indicator value
    
    # Signal: Cross above envelope (no future leak)
    enter_long = close_prev <= basis_prev and close_now > basis_now
    
    return {"enter_long": enter_long}
```

### Execution Timeline

```
Bar 100: Close=100, Basis=102
  └─> Signal check: 100 <= 102? Yes, but close_now not > basis_now
  └─> on_bar returns: {"enter_long": False}

Bar 101: Close=103, Basis=102
  └─> Signals checked: close_prev(100) <= basis_prev(102)? Yes
  └─> close_now(103) > basis_now(102)? Yes ✅
  └─> on_bar returns: {"enter_long": True}
  └─> **SIGNAL GENERATED** at Bar 101 close

Bar 102: Open=103.5
  └─> Entry executed at 103.5 ✅
  └─> Position entry_price = 103.5
```

---

## Common Pitfalls to Avoid

### ❌ Lookahead Bias
```python
# WRONG - Leaks future data!
def on_bar(self, ts, row, state):
    idx = self.data.index.get_loc(ts)
    next_close = self.data.close.iloc[idx + 1]  # FUTURE!
    return {"enter_long": next_close > row.close}
```

### ❌ Using Next Bar Data
```python
# WRONG - Uses data not yet known!
def on_bar(self, ts, row, state):
    idx = self.data.index.get_loc(ts)
    next_high = self.data.high.iloc[idx + 1]    # FUTURE!
    next_low = self.data.low.iloc[idx + 1]      # FUTURE!
    return {"enter_long": next_high > next_low}
```

### ❌ Accessing Index Beyond Current
```python
# WRONG - May access beyond data length
def on_bar(self, ts, row, state):
    idx = self.data.index.get_loc(ts)
    return {"enter_long": self.data.close.iloc[idx + 5] > 100}  # FUTURE!
```

### ✅ Correct Approach
```python
# RIGHT - Only uses current and past bars
def on_bar(self, ts, row, state):
    idx = self.data.index.get_loc(ts)
    
    # Safe check for available history
    if idx < 5:
        return {"enter_long": False, "exit_long": False}
    
    # Only access bars [idx-5] through [idx]
    lookback_high = self.data.high.iloc[idx-5:idx].max()  # Past bars only!
    return {"enter_long": row.close > lookback_high}
```

---

## Implementation Checklist

- ✅ Signal generated: Current bar data
- ✅ Execution: Next bar open price
- ✅ No future data accessed: Only [idx-N] to [idx] (never [idx+1])
- ✅ Index bounds checked: `if idx < min_required_bars`
- ✅ State used: qty, cash, equity from `state` dict
- ✅ Return format: Dictionary with "enter_long", "exit_long" keys
- ✅ Previous bar available: Always check `idx > 0` before `iloc[idx-1]`

---

## Signal Timing Summary

| Event | Timing | Price |
|-------|--------|-------|
| **Signal Detection** | End of Bar N | Bar N Close |
| **Trade Execution** | Start of Bar N+1 | Bar N+1 Open |
| **Position Tracking** | Start of Bar N+1 | Based on N+1 Open |
| **Next Signal Check** | End of Bar N+1 | Bar N+1 Close |

---

## Related Files

- `core/strategy.py`: Strategy base class with `on_bar()` method
- `core/engine.py`: Backtesting engine (signal→execution logic)
- `strategies/envelope_kd.py`: Example implementation
- `strategies/ichimoku.py`: Another example

---

## FAQ

**Q: Why signal on current bar close but execute on next bar open?**
A: In real markets, you can't execute at the exact close time. Traders place orders based on analysis at close, then execution happens at next open.

**Q: Can I change this behavior?**
A: Yes! Check `config.py` for `execute_on_next_open` setting. But recommended: keep it True for realism.

**Q: What if I want same-bar execution?**
A: That would require access to future data (intrabar), causing lookahead bias. Not recommended.

**Q: How do I know what bar index I'm on?**
A: Use `idx = self.data.index.get_loc(ts)`. Then reference any previous bars safely.

---

*Last Updated: November 3, 2025*
