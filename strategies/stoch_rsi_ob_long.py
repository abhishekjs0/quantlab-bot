#!/usr/bin/env python3
"""
Stochastic RSI Overbought/Oversold Long-Only Strategy

Based on Stochastic RSI indicator with configurable entry/exit modes:
- Entry on oversold conditions (Enter Into Zone, Out Of Zone, or Turn In Zone)
- Exit on overbought conditions (Exit Into Zone, Out Of Zone, or Turn In Zone)
- Optional filters: Trend (EMA), Volatility (ATR), ADX, DI+/DI-
- Risk management via ATR-based stop loss

Default parameters: RSI(56)/Stoch(40)/Smooth(20) with 20/20 OB/OS levels
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from core.strategy import Strategy


class StochRSIOBLongStrategy(Strategy):
    """
    Stochastic RSI Overbought/Oversold Long-Only Strategy
    
    Generates long entry signals based on Stochastic RSI oversold conditions
    and exits on overbought conditions with optional trend, volatility, and
    momentum filters.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Initialize strategy with parameters
        
        Args:
            params: Strategy parameters including:
                - rsi_length: RSI period (default: 56)
                - stoch_length: Stochastic period (default: 40)
                - smooth_length: K smoothing period (default: 20)
                - ob_level: Overbought threshold (default: 20)
                - os_level: Oversold threshold (default: 20)
                - rsi_source: Price source for RSI (default: 'close')
                - entry_mode: Entry trigger mode (default: 'Enter Turn In Zone')
                - exit_mode: Exit trigger mode (default: 'Exit Turn In Zone')
                - use_atr_stop: Enable ATR stop loss (default: True)
                - atr_length_stop: ATR period for stop (default: 14)
                - atr_multiple_stop: ATR multiple for stop (default: 5)
                - use_trend_filter: Enable EMA trend filter (default: False)
                - trend_ema_length: EMA period for trend (default: 10)
                - use_vol_filter: Enable volatility filter (default: False)
                - atr_length_vol: ATR period for vol filter (default: 14)
                - atr_ma_length_vol: ATR MA period (default: 50)
                - use_adx_filter: Enable ADX filter (default: False)
                - adx_smoothing_length: ADX smoothing (default: 14)
                - di_length: DI period (default: 5)
                - adx_min: Minimum ADX value (default: 20)
                - adx_max: Maximum ADX value (default: 30)
                - use_di_filter: Enable DI+>DI- filter (default: False)
        """
        default_params = {
            # Core Stoch RSI parameters
            'rsi_length': 56,
            'stoch_length': 40,
            'smooth_length': 20,
            'ob_level': 20.0,
            'os_level': 20.0,
            'rsi_source': 'close',
            
            # Entry/Exit modes
            'entry_mode': 'Enter Turn In Zone',  # 'Enter Into Zone', 'Enter Out Of Zone', 'Enter Turn In Zone'
            'exit_mode': 'Exit Turn In Zone',     # 'Exit Into Zone', 'Exit Out Of Zone', 'Exit Turn In Zone'
            
            # Risk management
            'use_atr_stop': True,
            'atr_length_stop': 14,
            'atr_multiple_stop': 5.0,
            
            # Optional filters
            'use_trend_filter': False,
            'trend_ema_length': 10,
            
            'use_vol_filter': False,
            'atr_length_vol': 14,
            'atr_ma_length_vol': 50,
            
            'use_adx_filter': False,
            'adx_smoothing_length': 14,
            'di_length': 5,
            'adx_min': 20.0,
            'adx_max': 30.0,
            
            'use_di_filter': False,
        }
        
        if params:
            default_params.update(params)
        
        super().__init__(default_params)
        
        self.name = "Stochastic RSI OB/OS Long-Only"
        self.description = (
            f"Long-only strategy using Stochastic RSI({self.params['rsi_length']}, "
            f"{self.params['stoch_length']}, {self.params['smooth_length']}) with "
            f"OB/OS levels at {self.params['ob_level']}/{self.params['os_level']}"
        )
    
    def calculate_rsi(self, data: pd.DataFrame, column: str, period: int) -> pd.Series:
        """Calculate RSI indicator"""
        delta = data[column].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate_stoch_rsi(self, data: pd.DataFrame) -> tuple:
        """
        Calculate Stochastic RSI indicator
        
        Returns:
            tuple: (k, k_prev) - Current and previous K values
        """
        rsi_length = self.params['rsi_length']
        stoch_length = self.params['stoch_length']
        smooth_length = self.params['smooth_length']
        source = self.params['rsi_source']
        
        # Calculate RSI
        rsi = self.calculate_rsi(data, source, rsi_length)
        
        # Calculate Stochastic of RSI
        rsi_lowest = rsi.rolling(window=stoch_length, min_periods=stoch_length).min()
        rsi_highest = rsi.rolling(window=stoch_length, min_periods=stoch_length).max()
        
        denominator = rsi_highest - rsi_lowest
        stoch_raw = np.where(
            denominator != 0.0,
            (rsi - rsi_lowest) / denominator * 100.0,
            0.0
        )
        
        # Smooth to get %K
        k = pd.Series(stoch_raw, index=data.index).rolling(
            window=smooth_length, 
            min_periods=smooth_length
        ).mean()
        
        k_prev = k.shift(1)
        
        return k, k_prev
    
    def calculate_atr(self, data: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range"""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift(1))
        low_close = np.abs(data['low'] - data['close'].shift(1))
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        return atr
    
    def calculate_adx_di(self, data: pd.DataFrame) -> tuple:
        """
        Calculate ADX and Directional Indicators
        
        Returns:
            tuple: (adx, plus_di, minus_di)
        """
        di_length = self.params['di_length']
        adx_smoothing = self.params['adx_smoothing_length']
        
        # Calculate directional movements
        up = data['high'].diff()
        down = -data['low'].diff()
        
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        
        # Calculate True Range
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift(1))
        low_close = np.abs(data['low'] - data['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # RMA (EMA with alpha = 1/period)
        tr_rma = tr.ewm(alpha=1/di_length, min_periods=di_length, adjust=False).mean()
        plus_dm_rma = pd.Series(plus_dm, index=data.index).ewm(
            alpha=1/di_length, min_periods=di_length, adjust=False
        ).mean()
        minus_dm_rma = pd.Series(minus_dm, index=data.index).ewm(
            alpha=1/di_length, min_periods=di_length, adjust=False
        ).mean()
        
        # Calculate DI
        plus_di = 100 * plus_dm_rma / tr_rma
        minus_di = 100 * minus_dm_rma / tr_rma
        
        # Calculate ADX
        sum_di = plus_di + minus_di
        dx = 100 * np.abs(plus_di - minus_di) / np.where(sum_di == 0, 1, sum_di)
        adx = dx.ewm(alpha=1/adx_smoothing, min_periods=adx_smoothing, adjust=False).mean()
        
        return adx, plus_di, minus_di
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        df = data.copy()
        
        # Stochastic RSI
        k, k_prev = self.calculate_stoch_rsi(df)
        df['stoch_rsi_k'] = k
        df['stoch_rsi_k_prev'] = k_prev
        
        # ATR for stop loss
        if self.params['use_atr_stop']:
            df['atr_stop'] = self.calculate_atr(df, self.params['atr_length_stop'])
        
        # Trend filter: EMA
        if self.params['use_trend_filter']:
            df['ema_trend'] = df['close'].ewm(
                span=self.params['trend_ema_length'], 
                adjust=False
            ).mean()
        
        # Volatility filter: ATR > ATR MA
        if self.params['use_vol_filter']:
            atr_vol = self.calculate_atr(df, self.params['atr_length_vol'])
            df['atr_vol'] = atr_vol
            df['atr_vol_ma'] = atr_vol.rolling(
                window=self.params['atr_ma_length_vol']
            ).mean()
        
        # ADX and DI filters
        if self.params['use_adx_filter'] or self.params['use_di_filter']:
            adx, plus_di, minus_di = self.calculate_adx_di(df)
            df['adx'] = adx
            df['plus_di'] = plus_di
            df['minus_di'] = minus_di
        
        return df
    
    def check_entry_signal(self, row: pd.Series) -> bool:
        """
        Check if entry conditions are met
        
        Args:
            row: Current data row with indicators
            
        Returns:
            bool: True if entry signal present
        """
        k = row['stoch_rsi_k']
        k_prev = row['stoch_rsi_k_prev']
        os_level = self.params['os_level']
        entry_mode = self.params['entry_mode']
        
        # Check for NaN values
        if pd.isna(k) or pd.isna(k_prev):
            return False
        
        # Entry signal based on mode
        entry_signal = False
        
        if entry_mode == 'Enter Into Zone':
            # Enter when Stoch RSI drops into oversold zone
            entry_signal = (k_prev > os_level) and (k <= os_level)
        
        elif entry_mode == 'Enter Out Of Zone':
            # Enter when Stoch RSI leaves oversold zone (mean reversion)
            entry_signal = (k_prev <= os_level) and (k > os_level)
        
        elif entry_mode == 'Enter Turn In Zone':
            # Enter on turning point inside oversold zone
            entry_signal = (k <= os_level) and (k_prev <= os_level) and (k > k_prev)
        
        if not entry_signal:
            return False
        
        # Apply filters
        # Trend filter
        if self.params['use_trend_filter']:
            if pd.isna(row['ema_trend']) or row['close'] <= row['ema_trend']:
                return False
        
        # Volatility filter
        if self.params['use_vol_filter']:
            if pd.isna(row['atr_vol']) or pd.isna(row['atr_vol_ma']):
                return False
            if row['atr_vol'] <= row['atr_vol_ma']:
                return False
        
        # ADX filter
        if self.params['use_adx_filter']:
            if pd.isna(row['adx']):
                return False
            if not (self.params['adx_min'] <= row['adx'] <= self.params['adx_max']):
                return False
        
        # DI filter
        if self.params['use_di_filter']:
            if pd.isna(row['plus_di']) or pd.isna(row['minus_di']):
                return False
            if row['plus_di'] <= row['minus_di']:
                return False
        
        return True
    
    def check_exit_signal(self, row: pd.Series) -> bool:
        """
        Check if exit conditions are met
        
        Args:
            row: Current data row with indicators
            
        Returns:
            bool: True if exit signal present
        """
        k = row['stoch_rsi_k']
        k_prev = row['stoch_rsi_k_prev']
        ob_level = self.params['ob_level']
        exit_mode = self.params['exit_mode']
        
        # Check for NaN values
        if pd.isna(k) or pd.isna(k_prev):
            return False
        
        # Exit signal based on mode
        exit_signal = False
        
        if exit_mode == 'Exit Into Zone':
            # Exit when Stoch RSI enters overbought zone
            exit_signal = (k_prev < ob_level) and (k >= ob_level)
        
        elif exit_mode == 'Exit Out Of Zone':
            # Exit when Stoch RSI leaves overbought zone
            exit_signal = (k_prev >= ob_level) and (k < ob_level)
        
        elif exit_mode == 'Exit Turn In Zone':
            # Exit on turning point inside overbought zone
            exit_signal = (k >= ob_level) and (k_prev >= ob_level) and (k < k_prev)
        
        return exit_signal
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Stochastic RSI
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            DataFrame with signals and indicators
        """
        df = self.calculate_indicators(data)
        
        # Initialize signal columns
        df['signal'] = 0
        df['position'] = 0
        df['stop_loss'] = np.nan
        
        # Track position
        in_position = False
        entry_price = None
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            if not in_position:
                # Check for entry signal
                if self.check_entry_signal(row):
                    df.loc[df.index[i], 'signal'] = 1
                    df.loc[df.index[i], 'position'] = 1
                    in_position = True
                    entry_price = row['close']
                    
                    # Set stop loss if enabled
                    if self.params['use_atr_stop'] and not pd.isna(row['atr_stop']):
                        stop_price = entry_price - (
                            self.params['atr_multiple_stop'] * row['atr_stop']
                        )
                        df.loc[df.index[i], 'stop_loss'] = stop_price
            
            else:
                # In position - check for exit
                df.loc[df.index[i], 'position'] = 1
                
                # Carry forward stop loss
                if i > 0 and not pd.isna(df.iloc[i-1]['stop_loss']):
                    df.loc[df.index[i], 'stop_loss'] = df.iloc[i-1]['stop_loss']
                
                # Check zone-based exit
                if self.check_exit_signal(row):
                    df.loc[df.index[i], 'signal'] = -1
                    df.loc[df.index[i], 'position'] = 0
                    in_position = False
                    entry_price = None
                
                # Check ATR stop loss
                elif (self.params['use_atr_stop'] and 
                      not pd.isna(df.iloc[i]['stop_loss']) and 
                      row['low'] <= df.iloc[i]['stop_loss']):
                    df.loc[df.index[i], 'signal'] = -1
                    df.loc[df.index[i], 'position'] = 0
                    in_position = False
                    entry_price = None
        
        return df
    
    def get_parameter_ranges(self) -> Dict[str, tuple]:
        """
        Get parameter ranges for optimization
        
        Returns:
            Dictionary of parameter names and their (min, max, step) ranges
        """
        return {
            'rsi_length': (10, 100, 5),
            'stoch_length': (5, 50, 5),
            'smooth_length': (3, 30, 2),
            'ob_level': (60.0, 95.0, 5.0),
            'os_level': (5.0, 40.0, 5.0),
            'atr_length_stop': (7, 28, 7),
            'atr_multiple_stop': (1.0, 5.0, 0.5),
            'trend_ema_length': (50, 400, 50),
            'atr_length_vol': (7, 28, 7),
            'atr_ma_length_vol': (20, 100, 20),
            'adx_smoothing_length': (7, 28, 7),
            'di_length': (7, 28, 7),
            'adx_min': (10.0, 30.0, 5.0),
            'adx_max': (30.0, 60.0, 10.0),
        }
