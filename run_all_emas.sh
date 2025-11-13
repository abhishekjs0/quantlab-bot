#!/bin/bash

# Array of EMA combinations (short, long)
declare -a COMBINATIONS=(
    "13 34"
    "13 55"
    "21 55"
    "21 89"
    "34 89"
    "34 144"
    "55 144"
    "55 233"
)

echo "=========================================="
echo "RUNNING ALL EMA COMBINATIONS"
echo "=========================================="

for combo in "${COMBINATIONS[@]}"; do
    read short long <<< "$combo"
    echo ""
    echo "[Test] EMA $short/$long"
    
    # Update strategy file
    python3 << PYEOF
from pathlib import Path
strategy_file = Path("strategies/ema_crossover_21_55.py")
content = strategy_file.read_text()
lines = content.split("\n")
new_lines = []
for line in lines:
    if "ema_fast_period = " in line and "self.ema_fast_period" not in line:
        new_lines.append(f"    ema_fast_period = $short")
    elif "ema_slow_period = " in line and "self.ema_slow_period" not in line:
        new_lines.append(f"    ema_slow_period = $long")
    else:
        new_lines.append(line)
strategy_file.write_text("\n".join(new_lines))
PYEOF
    
    # Run backtest
    python3 -m runners.run_basket --basket_file data/basket_largecap_highbeta.txt --strategy ema_crossover_21_55 --interval 1d --period max > /tmp/ema_${short}_${long}.log 2>&1
    
    echo "✓ Completed EMA $short/$long"
done

echo ""
echo "=========================================="
echo "ALL BACKTESTS COMPLETE"
echo "=========================================="
