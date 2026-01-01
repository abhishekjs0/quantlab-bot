#!/usr/bin/env python3
"""
Analyze MFE (Maximum Favorable Excursion) to find optimal TP combination.

Uses actual realized max profit potential from trades to recommend:
- TP1% (first take profit level)
- TP1_qty% (qty to exit at TP1)
- TP2% (second take profit level)
- TP2_qty% (qty to exit at TP2)
- Remaining qty exits at CLOSE
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = Path(__file__).parent

# Grid search parameters
TP1_RANGE = [5, 8, 10, 12, 15, 20]  # TP1 percentage
TP1_QTY_RANGE = [0.15, 0.20, 0.30, 0.40]  # qty % to exit at TP1
TP2_RANGE = [15, 20, 25, 30, 40]  # TP2 percentage
TP2_QTY_RANGE = [0.30, 0.40, 0.50, 0.60]  # qty % to exit at TP2

def load_trades():
    """Load consolidated trades."""
    trades_file = WORKSPACE / "reports/0102-0144-tema-lsma-crossover-main-1d/consolidated_trades_MAX.csv"
    
    if not trades_file.exists():
        logger.error(f"❌ File not found: {trades_file}")
        return None
    
    df = pd.read_csv(trades_file)
    logger.info(f"✅ Loaded {len(df)} records")
    
    # Keep only entry trades (skip exit records)
    entry_trades = df[df['Type'] == 'Entry long'].copy()
    logger.info(f"✅ Found {len(entry_trades)} entry trades")
    
    return entry_trades

def simulate_tp_exit(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct):
    """
    Simulate exiting with TP levels based on MFE.
    
    Logic:
    - If MFE >= TP1%, exit tp1_qty_pct at TP1%
    - If remaining qty MFE >= TP2%, exit tp2_qty_pct at TP2%
    - Rest exits at actual close (using Net P&L %)
    """
    
    results = []
    
    for idx, trade in trades_df.iterrows():
        mfe_pct = trade['MFE %']
        entry_price = trade['Price INR']
        actual_pnl_pct = trade['Net P&L %']
        actual_pnl = trade['Net P&L INR']
        qty = trade['Position size (qty)']
        
        if pd.isna(mfe_pct) or pd.isna(entry_price):
            continue
        
        # Remaining qty to exit
        remaining_qty = qty
        total_pnl = 0
        
        # TP1 exit
        if mfe_pct >= tp1_pct:
            exit_qty = qty * tp1_qty_pct
            exit_pnl = exit_qty * entry_price * (tp1_pct / 100)
            total_pnl += exit_pnl
            remaining_qty -= exit_qty
        
        # TP2 exit
        if mfe_pct >= tp2_pct:
            exit_qty = remaining_qty * tp2_qty_pct
            exit_pnl = exit_qty * entry_price * (tp2_pct / 100)
            total_pnl += exit_pnl
            remaining_qty -= exit_qty
        
        # Rest exits at close (actual PnL)
        if remaining_qty > 0:
            # Scale remaining qty's share of actual PnL proportionally
            close_pnl = remaining_qty * entry_price * (actual_pnl_pct / 100)
            total_pnl += close_pnl
        
        # Calculate final metrics
        total_pnl_pct = (total_pnl / (qty * entry_price)) * 100 if qty > 0 else 0
        is_profitable = total_pnl > 0
        
        results.append({
            'trade_num': trade['Trade #'],
            'symbol': trade['Symbol'],
            'entry_price': entry_price,
            'mfe_pct': mfe_pct,
            'simulated_pnl': total_pnl,
            'simulated_pnl_pct': total_pnl_pct,
            'profitable': is_profitable,
            'original_pnl': actual_pnl
        })
    
    return results

def evaluate_combination(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct):
    """Evaluate a single TP combination."""
    
    results = simulate_tp_exit(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct)
    
    if not results:
        return None
    
    df_results = pd.DataFrame(results)
    
    total_trades = len(df_results)
    winning_trades = df_results[df_results['profitable'] == True]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    # Profit factor
    winning_pnl = df_results[df_results['simulated_pnl'] > 0]['simulated_pnl'].sum()
    losing_pnl = abs(df_results[df_results['simulated_pnl'] <= 0]['simulated_pnl'].sum())
    profit_factor = (winning_pnl / losing_pnl) if losing_pnl > 0 else (winning_pnl / 0.01 if winning_pnl > 0 else 0)
    
    # Total P&L
    net_pnl = df_results['simulated_pnl'].sum()
    avg_pnl = net_pnl / total_trades if total_trades > 0 else 0
    
    return {
        'tp1_pct': tp1_pct,
        'tp1_qty_pct': tp1_qty_pct,
        'tp2_pct': tp2_pct,
        'tp2_qty_pct': tp2_qty_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'net_pnl': net_pnl,
        'avg_pnl': avg_pnl
    }

def run_analysis():
    """Run MFE-based analysis."""
    
    logger.info("\n" + "="*90)
    logger.info("📊 MFE-BASED TP OPTIMIZATION ANALYSIS")
    logger.info("="*90)
    
    # Load trades
    trades_df = load_trades()
    if trades_df is None:
        return
    
    logger.info("\n" + "="*90)
    logger.info("⚡ Testing all 480 TP combinations using MFE data")
    logger.info("="*90)
    
    all_results = []
    total = len(TP1_RANGE) * len(TP1_QTY_RANGE) * len(TP2_RANGE) * len(TP2_QTY_RANGE)
    current = 0
    
    for tp1_pct in TP1_RANGE:
        for tp1_qty_pct in TP1_QTY_RANGE:
            for tp2_pct in TP2_RANGE:
                for tp2_qty_pct in TP2_QTY_RANGE:
                    current += 1
                    
                    result = evaluate_combination(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct)
                    
                    if result:
                        all_results.append(result)
                        
                        if current % 120 == 0:  # Log every 120 combinations
                            pct = (current / total) * 100
                            logger.info(f"[{current:3d}/{total}] ({pct:5.1f}%) - TP1={tp1_pct}% WR={result['win_rate']:.1f}% PF={result['profit_factor']:.2f}")
    
    # Sort by profit factor, then win rate
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values(by=['profit_factor', 'win_rate'], ascending=[False, False])
    
    # Save results
    timestamp = datetime.now().strftime("%m%d-%H%M")
    csv_file = WORKSPACE / f"mfe_analysis_results_{timestamp}.csv"
    df_results.to_csv(csv_file, index=False)
    
    logger.info("\n" + "="*110)
    logger.info("TOP 15 BEST COMBINATIONS (ranked by Profit Factor, then Win Rate)")
    logger.info("="*110 + "\n")
    
    for rank, (idx, row) in enumerate(df_results.head(15).iterrows(), 1):
        logger.info(
            f"Rank {rank:2d} | TP1={row['tp1_pct']:5.0f}% (qty={row['tp1_qty_pct']:.0%}) | "
            f"TP2={row['tp2_pct']:5.0f}% (qty={row['tp2_qty_pct']:.0%}) | "
            f"WR={row['win_rate']:6.1f}% | PF={row['profit_factor']:6.2f} | "
            f"Trades={row['total_trades']:5.0f} | P&L=₹{row['net_pnl']:12,.0f}"
        )
    
    logger.info("\n" + "="*110)
    logger.info(f"📊 Results saved to: {csv_file}")
    logger.info("="*110 + "\n")
    
    # Recommend best
    best = df_results.iloc[0]
    remaining_qty_pct = 1.0 - best['tp1_qty_pct'] - best['tp2_qty_pct']
    
    logger.info(f"✅ RECOMMENDED COMBINATION (based on MFE analysis):")
    logger.info(f"   TP1: {best['tp1_pct']:.0f}% (exit {best['tp1_qty_pct']:.0%} of position)")
    logger.info(f"   TP2: {best['tp2_pct']:.0f}% (exit {best['tp2_qty_pct']:.0%} of position)")
    logger.info(f"   CLOSE: Exit remaining {remaining_qty_pct:.0%} of position at signal")
    logger.info(f"   ")
    logger.info(f"   Win Rate: {best['win_rate']:.1f}%")
    logger.info(f"   Profit Factor: {best['profit_factor']:.2f}")
    logger.info(f"   Total Trades: {best['total_trades']:.0f}")
    logger.info(f"   Net P&L: ₹{best['net_pnl']:,.0f}")
    logger.info(f"   Avg P&L per trade: ₹{best['avg_pnl']:,.0f}\n")

if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
