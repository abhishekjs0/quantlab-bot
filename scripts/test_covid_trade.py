import pandas as pd
from core.engine import BacktestEngine
from core.config import BrokerConfig
from strategies.bb_pyramid_30pct import BBPyramid30Pct
from core.loaders import load_many_india

# Load one symbol to check pyramiding
symbol = 'RELIANCE'
data_dict = load_many_india([symbol], interval='1d')
df = data_dict[symbol]

# Monkey patch the strategy to add detailed debug output
class DebugBBPyramid(BBPyramid30Pct):
    scale_events = []
    
    def on_bar(self, ts, row, state):
        result = super().on_bar(ts, row, state)
        
        qty = state.get("qty", 0)
        in_position = qty > 0
        
        # Track ALL scale-in opportunities with full details
        if in_position and not self._scaled_in and self._first_fill_price is not None:
            scale_trigger = self._first_fill_price * (1.0 - self.scale_drop_pct)
            scale_hit = row.low <= scale_trigger
            
            weekly_bb_lower = self._daily_to_week_map['bb_lower'].get(ts)
            below_lower_bb = (weekly_bb_lower is not None and 
                            not pd.isna(weekly_bb_lower) and 
                            row.close < weekly_bb_lower)
            
            drop_pct = ((self._first_fill_price - row.low) / self._first_fill_price) * 100
            
            self.scale_events.append({
                'date': ts,
                'first_fill': self._first_fill_price,
                'low': row.low,
                'close': row.close,
                'drop_pct': drop_pct,
                'scale_trigger': scale_trigger,
                'scale_hit': scale_hit,
                'bb_lower': weekly_bb_lower,
                'below_bb': below_lower_bb,
                'would_scale': scale_hit and below_lower_bb,
                'action': result.get('signal_reason', 'holding')
            })
        
        return result

# Run backtest
cfg = BrokerConfig()
strategy = DebugBBPyramid()
engine = BacktestEngine(df, strategy, cfg, symbol=symbol)
trades, equity_df, signals_df = engine.run()

print(f'\n=== ALL TRADES: {len(trades)} ===')
print(trades[['entry_time', 'exit_time', 'entry_price', 'exit_price', 'entry_qty']].to_string())

print(f'\n=== COVID TRADE (Entry 2020-03-16) SCALE-IN ATTEMPTS ===')
covid_checks = [e for e in strategy.scale_events if e['date'] >= pd.Timestamp('2020-03-16') and e['date'] <= pd.Timestamp('2020-04-30')]
if len(covid_checks) > 0:
    covid_df = pd.DataFrame(covid_checks)
    print(covid_df[['date', 'first_fill', 'low', 'drop_pct', 'scale_hit', 'below_bb', 'would_scale', 'action']].to_string())
    print(f'\nMax drop: {covid_df["drop_pct"].max():.2f}%')
    print(f'Scale trigger hit: {covid_df["scale_hit"].sum()} times')
    print(f'Would scale (hit + below BB): {covid_df["would_scale"].sum()} times')
else:
    print('No scale-in checks during COVID trade period')

print(f'\n=== ALL SCALE-IN EVENTS SUMMARY ===')
if len(strategy.scale_events) > 0:
    all_df = pd.DataFrame(strategy.scale_events)
    print(f'Total checks: {len(all_df)}')
    print(f'Max drop observed: {all_df["drop_pct"].max():.2f}%')
    print(f'Times scale trigger hit (30% drop): {all_df["scale_hit"].sum()}')
    print(f'Times would scale (hit + below BB): {all_df["would_scale"].sum()}')
    
    # Show any time we hit 30% drop
    big_drops = all_df[all_df['scale_hit'] == True]
    if len(big_drops) > 0:
        print(f'\n🔥 SCALE TRIGGERS (30%+ drops):')
        print(big_drops[['date', 'first_fill', 'low', 'drop_pct', 'below_bb', 'would_scale', 'action']].to_string())
