# Repository Architecture Refactor Plan

## Current State Issues

### 1. **Duplicate Indicator Libraries**
- ❌ `utils/__init__.py` (605 lines) - Contains basic indicators
- ❌ `utils/indicators.py` (850+ lines) - Contains advanced indicators
- **Problem**: Confusion about where to add new indicators, duplication risk

### 2. **Duplicate Optimization Files**
- ❌ `core/optimizer.py` - Original optimizer
- ❌ `core/enhanced_optimizer.py` - Enhanced version
- **Problem**: Unclear which to use, maintenance burden

### 3. **Duplicate Walk-Forward Files**
- ❌ `core/walk_forward.py` - Original implementation
- ❌ `core/walkforward_analyzer.py` - Alternative implementation
- **Problem**: Two implementations of same concept

### 4. **Calculations in Visualization Layer**
- ❌ `viz/tv_plot.py` line 8-13: Donchian channel calculations
- ❌ `viz/final_fixed_dashboard.py` line 457, 1684: Peak equity calculations
- **Problem**: Violates separation of concerns, makes testing harder

### 5. **Deleted Obsolete Files**
- ✅ `core/global_market_regime.py` - Deleted
- ✅ `core/market_regime.py` - Deleted
- ✅ `docs/MARKET_REGIME_GUIDE.md` - Deleted
- ✅ `core/pine_adapter.py` - Deleted
- ✅ `core/pine_ops.py` - Deleted
- ✅ Removed NSEAdvanceDecline, NIFTYPutCallRatio, VIXAnalysis from indicators.py

---

## Recommended Modular Architecture

```
quantlab-workspace/
├── core/                          # Core backtesting engine
│   ├── engine.py                  # Main backtesting engine
│   ├── strategy.py                # Base strategy class
│   ├── optimizer.py               # SINGLE optimizer (merge both)
│   ├── walk_forward.py            # SINGLE walk-forward (merge both)
│   ├── monitoring.py              # Performance monitoring
│   └── perf.py                    # Performance calculations
│
├── utils/                         # Utility functions
│   ├── __init__.py                # Basic utilities only
│   ├── indicators.py              # ALL technical indicators (single source)
│   ├── performance.py             # Performance metrics
│   └── strategy_manager.py        # Strategy management
│
├── viz/                           # Visualization ONLY (no calculations)
│   ├── equity_plot.py             # Equity curves
│   ├── heatmap.py                 # Heatmaps
│   ├── bokeh_charts.py            # Interactive charts
│   └── hybrid_dashboard.py        # SINGLE dashboard (merge all dashboard files)
│
├── strategies/                    # Strategy implementations
│   ├── ichimoku.py
│   └── template.py
│
├── runners/                       # Execution scripts
│   └── run_basket.py              # Main basket runner
│
└── data/                          # Data management
    └── loaders.py
```

---

## Refactoring Tasks

### Phase 1: Consolidate Indicators (COMPLETED ✅)
- [x] **Keep**: `utils/indicators.py` as SINGLE source of truth
- [x] **Move**: All indicators from `utils/__init__.py` → `utils/indicators.py`
- [x] **Update**: All imports to use `from utils.indicators import ...`
- [x] **Remove**: Indicator functions from `utils/__init__.py`
- [x] **Result**: ~850 lines in single file with comprehensive indicator set

### Phase 2: Consolidate Optimizers
- [ ] **Analyze**: Compare `optimizer.py` vs `enhanced_optimizer.py`
- [ ] **Merge**: Best features from both into single `core/optimizer.py`
- [ ] **Update**: All imports and usage
- [ ] **Delete**: `core/enhanced_optimizer.py`
- [ ] **Test**: Verify optimization still works

### Phase 3: Consolidate Walk-Forward
- [ ] **Analyze**: Compare `walk_forward.py` vs `walkforward_analyzer.py`
- [ ] **Merge**: Best features into single `core/walk_forward.py`
- [ ] **Update**: All imports and usage
- [ ] **Delete**: `core/walkforward_analyzer.py`
- [ ] **Test**: Verify walk-forward analysis works

### Phase 4: Fix Visualization Layer (HIGH PRIORITY 🚨)
- [ ] **Move**: Donchian calculation from `viz/tv_plot.py` → `utils/indicators.py`
- [ ] **Move**: Peak equity calculation to `core/perf.py` or `runners/run_basket.py`
- [ ] **Update**: Visualization files to receive pre-calculated data
- [ ] **Merge**: All dashboard files into single `viz/hybrid_dashboard.py`
- [ ] **Delete**: Duplicate dashboard files
- [ ] **Rule**: Visualization layer should ONLY render, never calculate

### Phase 5: Optimize Performance Calculations
- [ ] **Analyze**: What calculations are in `core/perf.py`
- [ ] **Move**: Trade-level calculations to `runners/run_basket.py`
- [ ] **Keep**: Portfolio-level metrics in `core/perf.py`
- [ ] **Create**: Clear separation: trades (run_basket) vs portfolio (perf)

---

## Benefits of Modular Architecture

1. **Single Source of Truth**
   - One place for indicators
   - One optimizer implementation
   - One walk-forward implementation

2. **Clear Separation of Concerns**
   - Calculations in utils/core
   - Visualization in viz (display only)
   - Execution in runners

3. **Easier Testing**
   - Test indicators independently
   - Test visualizations with mock data
   - Test optimizers in isolation

4. **Improved Maintainability**
   - Clear where to add new features
   - Reduced code duplication
   - Easier to debug

5. **Better Performance**
   - Pre-calculate once, visualize many times
   - Cacheable calculations
   - Parallel processing friendly

---

## Implementation Priority

### Immediate (This Session)
1. ✅ Remove obsolete files
2. ✅ Remove unnecessary indicators
3. 🔄 Fix visualization calculations

### Next Session
4. Consolidate optimizers
5. Consolidate walk-forward
6. Merge dashboard files

### Future
7. Add comprehensive tests
8. Add type hints throughout
9. Add docstring standardization

---

## Notes

- **Volatility**: Now based on ATR % (not VIX)
- **Trend**: Using Aroon indicator (Bull/Sideways/Bear)
- **Consolidated Trades CSV**: 67 columns with all optimization parameters
- **Performance**: Backtest runs successfully in ~11.5 seconds
