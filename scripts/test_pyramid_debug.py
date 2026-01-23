import pandas as pd
from core.engine import BacktestEngine
from core.config import BrokerConfig
from strategies.bb_pyramid_30pct import BBPyramid30Pct
from core.loaders import load_many_india

# Load one symbol to check pyramiding
symbol = 'RELIANCE'
data_dict = load_many_india([symbol], interval='1d')
df = data_dict[symbol]

# Monkey patch the strategy to add debug output
class DebugBBPyramid(BBPyramid30Pct):
    scale_checks = []
    
    def on_bar(self, ts, row, state):
        result = super().on_bar(ts, row, state)
        
        qty = state.get("qty", 0)
        in_position = qty > 0
        
        # Track scale-in checks
        if in_position and not self._scaled_in and self._first_fill_price is not None:
            scale_trigger = self._first_fill_price * (1.0 - self.scale_drop_pct)
            scale_hit = row.low <= scale_trigger
            drop_pct = ((self._first_fill_price - row.low) / self._first_fill_price) * 100
            
            self.scale_checks.append({
                'date': ts,
                'first_fill': self._first_fill_price,
                'current_low': row.low,
                'drop_pct': drop_pct,
                'scale_trigger': scale_trigger,
                'scale_hit': scale_hit,
                'result': result['signal_reason'] if result.get('enter_long') or result.get('exit_long') else 'holding'
            })
        
        return result

# Run backtest
cfg = BrokerConfig()
strategy = DebugBBPyramid()
engine = BacktestEngine(df, strategy, cfg, symbol=symbol)
trades, equity_df, signals_df = engine.run()

print(f'\n=== TRADES: {len(trades)} ===')
print(trades[['entry_time', 'exit_time', 'entry_price', 'entry_qty']].to_string())

print(f'\n=== SCALE-IN CHECKS: {len(strategy.scale_checks)} ===')
if len(strategy.scale_checks) > 0:
    checks_df = pd.DataFrame(strategy.scale_checks)
    print(checks_df.to_string())
    print(f'\nMax drop observed: {checks_df["drop_pct"].max():.2f}%')
    print(f'Times scale trigger hit: {checks_df["scale_hit"].sum()}')
else:
    print('NO scale-in checks recorded - positions exit before 30% drop opportunity')
