# 🎯 Quick Answer: NaN With 10 Years of Data

## TL;DR

**Does the new runner yield NaN for 5Y when you have 10 years in cache?**

### ❌ NO
- Strategy receives full 10 years of data
- All indicators calculated on full 10-year history
- Ichimoku warmup requires only ~52 bars
- By bar 52: all indicators ready, no NaN
- For entire 5Y window (1225 bars): all indicators valid

---

## Why NaN Checks Exist Then?

The NaN validation in the new code is **defensive programming**:

```python
# In strategies/ichimoku.py lines 225-231
if (
    np.isnan(self.conversion_line[idx])
    or np.isnan(self.base_line[idx])
    or np.isnan(self.leading_span_b[idx])
):
    return {"enter_long": False, "exit_long": False, "signal_reason": ""}
```

This is like a **safety belt that should never activate** when:
- ✅ You have sufficient historical data (10Y)
- ✅ Data is clean and continuous
- ✅ No gaps or corruptions

---

## What Actually Changed Between Reports

The 1 trade difference (40 → 39) is likely **NOT from NaN validation**:

### The Evidence

**Report 1104 (old code):**
- Generated 40 trades in 5Y window
- Includes suspicious TATASTEEL trade with entry_date = 2025-09-03 (FUTURE!)

**Report 1107 (new code):**
- Generated 39 trades in 5Y window  
- Either rejected the invalid trade OR it wasn't re-generated

**What this means:**
- NaN validation didn't reject trades (they're all valid)
- The difference is likely from how edge cases are handled
- Not from indicator NaN values

---

## Real Problem: Data Quality, Not NaN

The actual issue is:
1. ❌ Trade entry date in future (impossible)
2. ❌ Data validation missing
3. ❌ No checks for logical trade validity
4. ❌ NaN validation doesn't address this

The new NaN validation is **defensive but incomplete**. It handles one specific edge case (NaN indicators) but misses the real problem (invalid trade metadata).

---

## Bottom Line

| Scenario | With 10Y Data | NaN Validation Needed? |
|----------|---|---|
| All indicators ready by bar 52 | YES ✅ | NO ❌ |
| 5Y window has sufficient history | YES ✅ | NO ❌ |
| NaN validation should trigger | RARELY | NO ❌ |

**If you ARE seeing NaN validation trigger:** There's a bug in data loading or indicator calculation, not a limitation of 10Y data.

