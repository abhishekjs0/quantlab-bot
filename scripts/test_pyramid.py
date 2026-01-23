import pandas as pd
from core.engine import BacktestEngine
from core.config import BrokerConfig
from strategies.bb_pyramid_30pct import BBPyramid30Pct
from core.loaders import load_many_india

# Load one symbol to check pyramiding
symbol = 'RELIANCE'
data_dict = load_many_india([symbol], interval='1d')
df = data_dict[symbol]

# Run backtest
cfg = BrokerConfig()
strategy = BBPyramid30Pct()
engine = BacktestEngine(df, strategy, cfg, symbol=symbol)
trades, equity_df, signals_df = engine.run()

# Get trades and check for pyramiding
if len(trades) > 0:
    print('\nFirst 10 trades:')
    print(trades[['entry_time', 'exit_time', 'entry_price', 'exit_price', 'entry_qty', 'net_pnl']].head(10).to_string())
    print(f'\nTotal trades: {len(trades)}')
    
    # Check if any trades overlap (pyramiding indicator)
    trades_sorted = trades.sort_values('entry_time')
    pyramiding_found = False
    for i in range(len(trades_sorted)-1):
        exit_time = trades_sorted.iloc[i]['exit_time']
        next_entry = trades_sorted.iloc[i+1]['entry_time']
        if pd.notna(exit_time) and next_entry < exit_time:
            print(f'\n✓ PYRAMIDING DETECTED: Trade {i} exits at {exit_time}, Trade {i+1} enters at {next_entry}')
            print(trades_sorted.iloc[i:i+2][['entry_time', 'exit_time', 'entry_price', 'entry_qty']].to_string())
            pyramiding_found = True
            break
    
    if not pyramiding_found:
        print('\n✗ NO PYRAMIDING DETECTED - all trades are sequential (exit before next entry)')
        print('\nChecking entries_count attribute in strategy...')
        print(f'Strategy pyramiding attribute: {strategy.pyramiding}')
