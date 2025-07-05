import numpy as np
import pandas as pd
from typing import Union, List, Optional

def calculate_rsi(prices: Union[List[float], np.ndarray], period: int = 14) -> np.ndarray:
    """
    Calculate the Relative Strength Index (RSI) for a series of prices.
    
    Args:
        prices: Array of price values
        period: RSI period (default: 14)
        
    Returns:
        Array of RSI values
    """
    # Convert prices to numpy array if it's not already
    prices_array = np.array(prices)
    
    # Calculate price changes
    deltas = np.diff(prices_array)
    
    # Create arrays of gains and losses
    gains = np.zeros_like(deltas)
    losses = np.zeros_like(deltas)
    
    # Separate gains and losses
    gains[deltas > 0] = deltas[deltas > 0]
    losses[deltas < 0] = -deltas[deltas < 0]
    
    # Calculate average gains and losses
    avg_gain = np.zeros_like(prices_array)
    avg_loss = np.zeros_like(prices_array)
    
    # First average
    if len(gains) >= period:
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
    
    # Calculate remaining averages using Wilder's smoothing method
    for i in range(period + 1, len(prices_array)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
    
    # Calculate RS (Relative Strength)
    rs = np.zeros_like(prices_array)
    rs[avg_loss > 0] = avg_gain[avg_loss > 0] / avg_loss[avg_loss > 0]
    
    # Calculate RSI
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi

def add_rsi_to_dataframe(
    df: pd.DataFrame, 
    price_column: str = 'close', 
    period: int = 14,
    result_column: str = 'rsi'
) -> pd.DataFrame:
    """
    Add RSI values to a DataFrame.
    
    Args:
        df: DataFrame with price data
        price_column: Column name with price data (default: 'close')
        period: RSI period (default: 14)
        result_column: Column name for RSI values (default: 'rsi')
        
    Returns:
        DataFrame with RSI values added
    """
    if price_column not in df.columns:
        raise ValueError(f"Price column '{price_column}' not found in DataFrame")
    
    # Calculate RSI
    prices = df[price_column].values
    rsi_values = calculate_rsi(prices, period)
    
    # Add RSI to DataFrame
    result_df = df.copy()
    result_df[result_column] = rsi_values
    
    return result_df

def is_overbought(rsi_value: float, threshold: float = 70.0) -> bool:
    """
    Check if RSI value indicates overbought condition.
    
    Args:
        rsi_value: RSI value to check
        threshold: Overbought threshold (default: 70.0)
        
    Returns:
        True if overbought, False otherwise
    """
    return rsi_value >= threshold

def is_oversold(rsi_value: float, threshold: float = 30.0) -> bool:
    """
    Check if RSI value indicates oversold condition.
    
    Args:
        rsi_value: RSI value to check
        threshold: Oversold threshold (default: 30.0)
        
    Returns:
        True if oversold, False otherwise
    """
    return rsi_value <= threshold

def get_rsi_signal(
    rsi_value: float, 
    overbought_threshold: float = 70.0, 
    oversold_threshold: float = 30.0
) -> Optional[str]:
    """
    Get trading signal based on RSI value.
    
    Args:
        rsi_value: Current RSI value
        overbought_threshold: Overbought threshold (default: 70.0)
        oversold_threshold: Oversold threshold (default: 30.0)
        
    Returns:
        'BUY' for oversold, 'SELL' for overbought, None for neutral
    """
    if is_oversold(rsi_value, oversold_threshold):
        return "BUY"
    elif is_overbought(rsi_value, overbought_threshold):
        return "SELL"
    else:
        return None 