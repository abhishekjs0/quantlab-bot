#!/usr/bin/env python3
"""
Calculate KER (Kaufman Efficiency Ratio) for all symbols in all baskets.

KER measures the efficiency of price movement:
- KER = (Net Price Change) / (Sum of Absolute Price Changes)
- Range: 0 to 1
- Higher KER = More efficient trending (better for trend-following strategies)
- Lower KER = More choppy/noisy movement

This script calculates KER for the last 5 years (1225 bars) for each symbol
across all basket files to help with asset filtering for trend-following strategies.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.loaders import load_many_india

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_ker(prices: pd.Series, period: int = 10) -> float:
    """
    Calculate Kaufman Efficiency Ratio (KER) for a price series.
    
    Args:
        prices: Series of closing prices
        period: Number of periods to calculate KER over (default: 10)
    
    Returns:
        KER value between 0 and 1
    """
    if len(prices) < period + 1:
        return np.nan
    
    # Use the last 'period' prices
    price_data = prices.iloc[-period-1:]
    
    # Net change (absolute difference between first and last)
    net_change = abs(price_data.iloc[-1] - price_data.iloc[0])
    
    # Sum of absolute changes
    price_changes = price_data.diff().abs()
    volatility = price_changes.sum()
    
    # Avoid division by zero
    if volatility == 0:
        return 0.0
    
    ker = net_change / volatility
    return ker


def load_basket_symbols(basket_file: str) -> List[str]:
    """Load symbols from a basket file."""
    basket_path = project_root / "data" / basket_file
    
    if not basket_path.exists():
        logger.warning(f"Basket file not found: {basket_file}")
        return []
    
    with open(basket_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    return symbols


def calculate_symbol_ker(symbol: str, bars: int = 1225, ker_period: int = 10) -> Tuple[float, int]:
    """
    Calculate KER for a single symbol.
    
    Args:
        symbol: Stock symbol
        bars: Number of bars to fetch (default: 1225 for 5 years)
        ker_period: Period for KER calculation (default: 10)
    
    Returns:
        Tuple of (KER value, actual bars available)
    """
    try:
        # Fetch data using the same loader as the backtesting system
        data_dict = load_many_india(
            symbols=[symbol],
            interval='1d',
            period='max',
            use_cache_only=True
        )
        
        if not data_dict or symbol not in data_dict:
            logger.warning(f"No data available for {symbol}")
            return np.nan, 0
        
        df = data_dict[symbol]
        
        if df is None or df.empty:
            logger.warning(f"No data available for {symbol}")
            return np.nan, 0
        
        # Use only the last 'bars' rows
        if len(df) > bars:
            df = df.iloc[-bars:]
        
        actual_bars = len(df)
        
        if actual_bars < ker_period + 1:
            logger.warning(f"Insufficient data for {symbol}: {actual_bars} bars")
            return np.nan, actual_bars
        
        # Calculate KER using the full available period
        ker = calculate_ker(df['close'], period=actual_bars - 1)
        
        return ker, actual_bars
        
    except Exception as e:
        logger.error(f"Error calculating KER for {symbol}: {e}")
        return np.nan, 0


def main():
    """Main function to calculate KER for all baskets."""
    
    # Define all basket files
    basket_files = [
        'basket_largecap_highbeta.txt',
        'basket_largecap_lowbeta.txt',
        'basket_midcap_highbeta.txt',
        'basket_midcap_lowbeta.txt',
        'basket_smallcap_highbeta.txt',
        'basket_smallcap_lowbeta.txt',
    ]
    
    # Results storage
    all_results = []
    
    logger.info("=" * 80)
    logger.info("Starting KER Calculation for All Baskets")
    logger.info(f"Period: 5 years (1225 bars)")
    logger.info("=" * 80)
    
    # Process each basket
    for basket_file in basket_files:
        basket_name = basket_file.replace('basket_', '').replace('.txt', '')
        logger.info(f"\n📊 Processing basket: {basket_name}")
        
        # Load symbols
        symbols = load_basket_symbols(basket_file)
        logger.info(f"   Symbols to process: {len(symbols)}")
        
        if not symbols:
            continue
        
        # Calculate KER for each symbol
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"   [{i}/{len(symbols)}] Calculating KER for {symbol}...")
            
            ker, bars = calculate_symbol_ker(symbol, bars=1225)
            
            all_results.append({
                'Basket': basket_name,
                'Symbol': symbol,
                'KER_5Y': round(ker, 4) if not np.isnan(ker) else np.nan,
                'Bars_Available': bars,
                'Data_Quality': 'Good' if bars >= 1225 else 'Limited' if bars >= 500 else 'Poor'
            })
            
            if not np.isnan(ker):
                logger.info(f"   ✅ {symbol}: KER = {ker:.4f} ({bars} bars)")
            else:
                logger.info(f"   ❌ {symbol}: No KER calculated ({bars} bars)")
    
    # Create DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Sort by KER descending (best trending assets first)
    results_df = results_df.sort_values('KER_5Y', ascending=False, na_position='last')
    
    # Save to CSV
    output_file = project_root / 'reports' / 'basket_ker_analysis_5y.csv'
    results_df.to_csv(output_file, index=False)
    
    logger.info("\n" + "=" * 80)
    logger.info("KER Calculation Complete!")
    logger.info("=" * 80)
    logger.info(f"📁 Results saved to: {output_file}")
    
    # Print summary statistics
    logger.info("\n📊 Summary Statistics by Basket:")
    logger.info("-" * 80)
    
    for basket in results_df['Basket'].unique():
        basket_data = results_df[results_df['Basket'] == basket]
        valid_ker = basket_data['KER_5Y'].dropna()
        
        if len(valid_ker) > 0:
            logger.info(f"\n{basket.upper()}:")
            logger.info(f"  Total Symbols: {len(basket_data)}")
            logger.info(f"  Valid KER: {len(valid_ker)}")
            logger.info(f"  Average KER: {valid_ker.mean():.4f}")
            logger.info(f"  Median KER: {valid_ker.median():.4f}")
            logger.info(f"  Max KER: {valid_ker.max():.4f} ({basket_data.loc[basket_data['KER_5Y'].idxmax(), 'Symbol']})")
            logger.info(f"  Min KER: {valid_ker.min():.4f} ({basket_data.loc[basket_data['KER_5Y'].idxmin(), 'Symbol']})")
    
    # Overall statistics
    logger.info("\n" + "=" * 80)
    logger.info("📊 OVERALL STATISTICS:")
    logger.info("=" * 80)
    valid_all = results_df['KER_5Y'].dropna()
    logger.info(f"Total Symbols Analyzed: {len(results_df)}")
    logger.info(f"Valid KER Values: {len(valid_all)}")
    logger.info(f"Overall Average KER: {valid_all.mean():.4f}")
    logger.info(f"Overall Median KER: {valid_all.median():.4f}")
    
    # Top 10 trending assets
    logger.info("\n" + "=" * 80)
    logger.info("🏆 TOP 10 TRENDING ASSETS (Highest KER):")
    logger.info("=" * 80)
    top_10 = results_df.head(10)
    for idx, row in top_10.iterrows():
        logger.info(f"{row['Symbol']:15s} ({row['Basket']:25s}): KER = {row['KER_5Y']:.4f}")
    
    # Bottom 10 (most choppy)
    logger.info("\n" + "=" * 80)
    logger.info("⚠️  BOTTOM 10 ASSETS (Lowest KER - Most Choppy):")
    logger.info("=" * 80)
    bottom_10 = results_df[results_df['KER_5Y'].notna()].tail(10)
    for idx, row in bottom_10.iterrows():
        logger.info(f"{row['Symbol']:15s} ({row['Basket']:25s}): KER = {row['KER_5Y']:.4f}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Analysis Complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
