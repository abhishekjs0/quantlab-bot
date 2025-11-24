"""Test script to verify consolidated indicator calculations."""

import sys
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loaders import load_many_india
from runners.run_basket import _calculate_all_indicators_for_consolidated

def test_indicator_calculation():
    """Test indicator calculation on a single stock."""
    
    print("🧪 Testing consolidated indicator calculation...\n")
    
    # Load a single stock for testing
    test_symbol = "RELIANCE"
    print(f"Loading data for {test_symbol}...")
    
    try:
        data_dict = load_many_india(
            [test_symbol],
            interval="1d",
            period="1y",
            cache=True,
            use_cache_only=True
        )
        
        if test_symbol not in data_dict:
            print(f"❌ Could not load {test_symbol}")
            return False
        
        df = data_dict[test_symbol]
        print(f"✅ Loaded {len(df)} bars of data")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}\n")
        
        # Calculate all indicators
        print("Calculating all indicators...")
        df_with_indicators = _calculate_all_indicators_for_consolidated(df)
        
        print(f"✅ Calculated indicators successfully!")
        print(f"   Total columns: {len(df_with_indicators.columns)}")
        print(f"   Original OHLCV: {len(df.columns)} columns")
        print(f"   Added indicators: {len(df_with_indicators.columns) - len(df.columns)} columns\n")
        
        # Check key indicator categories
        print("📊 Indicator columns by category:")
        
        regime_cols = [col for col in df_with_indicators.columns if any(x in col for x in ['india_vix', 'nifty200', 'aroon', 'volatility'])]
        print(f"\n  Regime Filters ({len(regime_cols)} columns):")
        for col in sorted(regime_cols):
            print(f"    - {col}")
        
        trend_cols = [col for col in df_with_indicators.columns if any(x in col for x in ['adx', 'di_bullish', 'bull_bear'])]
        print(f"\n  Trend Strength ({len(trend_cols)} columns):")
        for col in sorted(trend_cols):
            print(f"    - {col}")
        
        momentum_cols = [col for col in df_with_indicators.columns if any(x in col for x in ['rsi', 'macd', 'cci', 'stoch'])]
        print(f"\n  Momentum ({len(momentum_cols)} columns):")
        for col in sorted(momentum_cols):
            print(f"    - {col}")
        
        structure_cols = [col for col in df_with_indicators.columns if any(x in col for x in ['ema', 'kijun', 'tenkan', 'bb_position', 'price_above'])]
        print(f"\n  Trend Structure ({len(structure_cols)} columns):")
        for col in sorted(structure_cols):
            print(f"    - {col}")
        
        volume_cols = [col for col in df_with_indicators.columns if any(x in col for x in ['mfi', 'cmf'])]
        print(f"\n  Volume ({len(volume_cols)} columns):")
        for col in sorted(volume_cols):
            print(f"    - {col}")
        
        # Show sample values from latest date
        print(f"\n📋 Sample values (latest date: {df_with_indicators.index[-1]}):")
        latest = df_with_indicators.iloc[-1]
        
        print(f"\n  OHLCV:")
        print(f"    close: {latest['close']:.2f}")
        print(f"    volume: {latest['volume']:.0f}")
        
        print(f"\n  Regime:")
        print(f"    india_vix: {latest.get('india_vix', 'N/A')}")
        print(f"    nifty200_above_ema20: {latest.get('nifty200_above_ema20', 'N/A')}")
        print(f"    short_trend_aroon25: {latest.get('short_trend_aroon25', 'N/A')}")
        print(f"    volatility_14: {latest.get('volatility_14', 'N/A')}")
        
        print(f"\n  Trend Strength:")
        print(f"    adx_14: {latest.get('adx_14', 'N/A'):.2f}")
        print(f"    di_bullish_14: {latest.get('di_bullish_14', 'N/A')}")
        
        print(f"\n  Momentum:")
        print(f"    rsi_14: {latest.get('rsi_14', 'N/A'):.2f}")
        print(f"    macd_bullish_12_26_9: {latest.get('macd_bullish_12_26_9', 'N/A')}")
        print(f"    cci_20: {latest.get('cci_20', 'N/A'):.2f}")
        
        print(f"\n  Trend Structure:")
        print(f"    price_above_ema20: {latest.get('price_above_ema20', 'N/A')}")
        print(f"    price_above_ema50: {latest.get('price_above_ema50', 'N/A')}")
        print(f"    bb_position_20_2: {latest.get('bb_position_20_2', 'N/A')}")
        
        print(f"\n  Volume:")
        print(f"    mfi_20: {latest.get('mfi_20', 'N/A'):.2f}")
        print(f"    cmf_20: {latest.get('cmf_20', 'N/A'):.4f}")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        import traceback
        print(f"\n❌ Test failed: {e}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_indicator_calculation()
    sys.exit(0 if success else 1)
