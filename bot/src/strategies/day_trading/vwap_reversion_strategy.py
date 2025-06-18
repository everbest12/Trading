#!/usr/bin/env python3
"""
VWAP Reversion Strategy

This strategy trades mean reversion to the Volume Weighted Average Price (VWAP)
for liquid equities during the trading day.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time, timedelta
import pytz
import pandas as pd
import numpy as np

from src.strategies.day_trading.day_strategy_base import DayStrategyBase
from src.brokers.mt5_connector import MT5Connector
from src.utils.logger import setup_logger

class VWAPReversionStrategy(DayStrategyBase):
    """
    A day trading strategy that trades mean reversion to the VWAP for equities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the VWAP reversion strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__(config)
        
        # Strategy-specific configuration
        self.symbols = config.get("symbols", ["AAPL", "MSFT", "GOOGL", "AMZN", "META"])
        self.vwap_deviation = config.get("vwap_deviation", 1.5)  # Standard deviations from VWAP to trigger entry
        self.profit_target = config.get("profit_target", 0.5)  # Target profit as percentage of VWAP deviation
        self.stop_loss = config.get("stop_loss", 1.0)  # Stop loss as percentage of VWAP deviation
        self.timeframe = config.get("timeframe", "M5")  # 5-minute timeframe
        self.min_volume = config.get("min_volume", 100000)  # Minimum volume for liquidity
        self.max_position_size = config.get("max_position_size", 100)  # Maximum position size in shares
        
        # VWAP calculation parameters
        self.lookback_periods = config.get("lookback_periods", 20)  # Number of periods for VWAP calculation
        self.bollinger_periods = config.get("bollinger_periods", 20)  # Periods for Bollinger Bands
        self.bollinger_std = config.get("bollinger_std", 2.0)  # Standard deviations for Bollinger Bands
        
        # Market data
        self.market_data = {}
        self.vwap_data = {}
        
        # Broker connection
        self.broker = None
        self.mt5_config_path = config.get("mt5_config_path", "config/brokers/mt5_config.json")
        
    def initialize(self) -> bool:
        """
        Initialize the VWAP reversion strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing VWAP reversion strategy")
        
        # Initialize broker connection
        try:
            self.broker = MT5Connector(self.mt5_config_path)
            if not self.broker.connect():
                self.logger.error("Failed to connect to MT5")
                return False
                
            self.logger.info(f"Connected to MT5: {self.broker.account_info['name']}")
        except Exception as e:
            self.logger.error(f"Error connecting to broker: {str(e)}")
            return False
            
        # Initialize parent
        return super().initialize()
    
    def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze the market conditions for day trading using VWAP.
        
        Returns:
            Dict: Analysis results
        """
        # Call parent method to handle day trading specific analysis
        analysis = super().analyze_market()
        
        # Only proceed with VWAP analysis if market is open
        if analysis["is_open"]:
            self._update_market_data()
            self._calculate_vwap()
            
            # Add VWAP specific analysis
            vwap_analysis = {}
            
            for symbol in self.symbols:
                if symbol in self.vwap_data:
                    vwap_info = self.vwap_data[symbol]
                    
                    vwap_analysis[symbol] = {
                        "vwap": vwap_info.get("vwap", 0),
                        "price": vwap_info.get("current_price", 0),
                        "deviation": vwap_info.get("deviation", 0),
                        "upper_band": vwap_info.get("upper_band", 0),
                        "lower_band": vwap_info.get("lower_band", 0),
                        "signal": vwap_info.get("signal", "none")
                    }
            
            analysis["vwap_analysis"] = vwap_analysis
        
        return analysis
    
    def _update_market_data(self) -> None:
        """Update market data for all symbols."""
        if not self.broker:
            return
            
        for symbol in self.symbols:
            try:
                # Get historical data
                data = self.broker.get_historical_data(
                    symbol,
                    self.timeframe,
                    self.lookback_periods + 10  # Add buffer
                )
                
                if data is not None and not data.empty:
                    # Store the data
                    self.market_data[symbol] = data
            except Exception as e:
                self.logger.error(f"Error updating market data for {symbol}: {str(e)}")
    
    def _calculate_vwap(self) -> None:
        """Calculate VWAP and Bollinger Bands for all symbols with available data."""
        for symbol, data in self.market_data.items():
            try:
                if data is None or data.empty:
                    continue
                    
                # Calculate VWAP
                data = data.copy()
                data['typical_price'] = (data['high'] + data['low'] + data['close']) / 3
                data['volume_price'] = data['typical_price'] * data['tick_volume']
                
                # Calculate cumulative values
                data['cumulative_volume'] = data['tick_volume'].cumsum()
                data['cumulative_volume_price'] = data['volume_price'].cumsum()
                
                # Calculate VWAP
                data['vwap'] = data['cumulative_volume_price'] / data['cumulative_volume']
                
                # Calculate standard deviation of price from VWAP
                data['price_vwap_diff'] = data['close'] - data['vwap']
                
                # Calculate Bollinger Bands around VWAP
                rolling_std = data['price_vwap_diff'].rolling(window=self.bollinger_periods).std()
                data['upper_band'] = data['vwap'] + (rolling_std * self.bollinger_std)
                data['lower_band'] = data['vwap'] - (rolling_std * self.bollinger_std)
                
                # Get latest values
                latest = data.iloc[-1]
                
                # Get current price
                current_price = latest['close']
                vwap = latest['vwap']
                upper_band = latest['upper_band']
                lower_band = latest['lower_band']
                
                # Calculate deviation from VWAP (in standard deviations)
                if rolling_std.iloc[-1] > 0:
                    deviation = (current_price - vwap) / rolling_std.iloc[-1]
                else:
                    deviation = 0
                
                # Determine signal
                signal = "none"
                if current_price <= lower_band and deviation <= -self.vwap_deviation:
                    signal = "buy"  # Price below lower band, potential buy
                elif current_price >= upper_band and deviation >= self.vwap_deviation:
                    signal = "sell"  # Price above upper band, potential sell
                
                # Calculate recent volume average
                recent_volume_avg = data['tick_volume'].tail(5).mean()
                
                # Store VWAP data
                self.vwap_data[symbol] = {
                    "vwap": vwap,
                    "current_price": current_price,
                    "upper_band": upper_band,
                    "lower_band": lower_band,
                    "deviation": deviation,
                    "signal": signal,
                    "std": rolling_std.iloc[-1],
                    "volume": recent_volume_avg
                }
                
            except Exception as e:
                self.logger.error(f"Error calculating VWAP for {symbol}: {str(e)}")
    
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on VWAP deviations.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        # First call parent method to apply day trading constraints
        parent_signals = super().generate_signals()
        
        # If parent says no trading, respect that
        if not parent_signals and len(parent_signals) == 0:
            return []
        
        signals = []
        
        # Check for new trade opportunities
        for symbol, vwap_info in self.vwap_data.items():
            try:
                signal = vwap_info.get("signal", "none")
                
                # Skip if no signal or insufficient volume
                if signal == "none" or vwap_info.get("volume", 0) < self.min_volume:
                    continue
                
                # Check if we already have a position in this symbol
                if self._has_open_position(symbol):
                    continue
                
                current_price = vwap_info["current_price"]
                vwap = vwap_info["vwap"]
                std = vwap_info["std"]
                
                # Calculate entry, stop loss, and take profit prices
                if signal == "buy":
                    entry_price = current_price
                    stop_loss = entry_price - (std * self.stop_loss)
                    take_profit = vwap  # Target VWAP as profit target
                    
                elif signal == "sell":
                    entry_price = current_price
                    stop_loss = entry_price + (std * self.stop_loss)
                    take_profit = vwap  # Target VWAP as profit target
                else:
                    continue
                
                # Calculate risk in dollars
                risk_per_share = abs(entry_price - stop_loss)
                
                # Calculate position size based on risk
                account_info = self.broker.get_account_info() if self.broker else {"balance": 10000}
                risk_amount = account_info["balance"] * (self.risk_per_trade / 100)
                
                # Calculate position size
                position_size = min(
                    int(risk_amount / risk_per_share),
                    self.max_position_size
                )
                
                # Ensure minimum position size
                if position_size < 1:
                    position_size = 1
                
                # Create signal
                trade_signal = {
                    "symbol": symbol,
                    "type": "market",
                    "action": signal,
                    "size": position_size,
                    "price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "reason": f"VWAP reversion ({signal})",
                    "vwap": vwap,
                    "deviation": vwap_info["deviation"]
                }
                
                signals.append(trade_signal)
                
                self.logger.info(f"Generated {signal} signal for {symbol} at {entry_price:.2f}, size: {position_size}, " +
                                f"SL: {stop_loss:.2f}, TP: {take_profit:.2f}, deviation: {vwap_info['deviation']:.2f} σ")
                
            except Exception as e:
                self.logger.error(f"Error generating signal for {symbol}: {str(e)}")
        
        return signals
    
    def _has_open_position(self, symbol: str) -> bool:
        """
        Check if we already have an open position for a symbol.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            bool: True if we have an open position, False otherwise
        """
        # Check in our local open_positions list
        for position in self.open_positions:
            if position.get("symbol") == symbol:
                return True
        
        # Double-check with broker if available
        if self.broker:
            positions = self.broker.get_open_positions()
            
            for position in positions:
                if position.get("symbol") == symbol:
                    return True
        
        return False
    
    def execute_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute the generated signals by placing orders with the broker.
        
        Args:
            signals: List of signals to execute
            
        Returns:
            List[Dict]: Results of the execution attempts
        """
        results = []
        
        if not self.broker:
            return results
            
        for signal in signals:
            try:
                symbol = signal.get("symbol", "")
                action = signal.get("action", "")
                size = signal.get("size", 0)
                stop_loss = signal.get("stop_loss", 0)
                take_profit = signal.get("take_profit", 0)
                
                # Check for valid parameters
                if not symbol or not action or size <= 0:
                    continue
                    
                # Execute the trade
                result = None
                if action == "buy":
                    result = self.broker.open_buy_position(symbol, size, stop_loss, take_profit)
                elif action == "sell":
                    result = self.broker.open_sell_position(symbol, size, stop_loss, take_profit)
                    
                if result and result.get("ticket", 0) > 0:
                    self.logger.info(f"Executed {action} order for {symbol}, size: {size}, ticket: {result['ticket']}")
                    
                    # Add execution result
                    execution_result = {
                        "symbol": symbol,
                        "action": action,
                        "size": size,
                        "price": result.get("price", 0),
                        "ticket": result.get("ticket", 0),
                        "time": datetime.now(),
                        "type": "new_position",
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "reason": signal.get("reason", "")
                    }
                    
                    results.append(execution_result)
                else:
                    self.logger.error(f"Failed to execute {action} order for {symbol}")
                    
            except Exception as e:
                self.logger.error(f"Error executing signal: {str(e)}")
                
        return results
    
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage existing positions with VWAP-based adjustments.
        
        Returns:
            List[Dict]: Results of position management actions
        """
        # First call parent method to handle day trading specific position management
        parent_results = super().manage_positions()
        
        results = list(parent_results) if parent_results else []
        
        if not self.broker:
            return results
            
        # Get all open positions
        open_positions = self.broker.get_open_positions()
        
        for position in open_positions:
            try:
                symbol = position.get("symbol", "")
                ticket = position.get("ticket", 0)
                
                # Skip symbols not in our strategy
                if symbol not in self.symbols:
                    continue
                    
                # Get current price and VWAP data
                if symbol not in self.vwap_data:
                    continue
                    
                vwap_info = self.vwap_data[symbol]
                current_price = vwap_info.get("current_price", 0)
                vwap = vwap_info.get("vwap", 0)
                
                # Determine position direction
                position_type = position.get("type", "")
                is_buy = position_type == "buy"
                
                # Check if price has reached VWAP (our target)
                if (is_buy and current_price >= vwap) or (not is_buy and current_price <= vwap):
                    # Close the position
                    result = self.broker.close_position(ticket)
                    
                    if result:
                        profit = result.get("profit", 0)
                        self.logger.info(f"Closed position {ticket} at VWAP, profit: {profit:.2f}")
                        
                        # Add result
                        close_result = {
                            "symbol": symbol,
                            "ticket": ticket,
                            "action": "close",
                            "profit": profit,
                            "time": datetime.now(),
                            "type": "close_position",
                            "reason": "Price reached VWAP target"
                        }
                        
                        results.append(close_result)
                
                # Adjust stop loss as price moves toward VWAP
                if symbol in self.market_data and not self.market_data[symbol].empty:
                    std = vwap_info.get("std", 0)
                    
                    if std > 0:
                        current_sl = position.get("sl", 0)
                        entry_price = position.get("open_price", 0)
                        
                        # Calculate new stop loss
                        new_sl = current_sl
                        
                        if is_buy:
                            # For buy positions, move stop loss up as price increases
                            midpoint = (entry_price + vwap) / 2
                            
                            if current_price > midpoint and current_sl < entry_price:
                                # Move to breakeven
                                new_sl = entry_price
                            
                        else:
                            # For sell positions, move stop loss down as price decreases
                            midpoint = (entry_price + vwap) / 2
                            
                            if current_price < midpoint and current_sl > entry_price:
                                # Move to breakeven
                                new_sl = entry_price
                        
                        # Update stop loss if changed
                        if new_sl != current_sl:
                            result = self.broker.modify_position(ticket, new_sl, position.get("tp", 0))
                            
                            if result:
                                self.logger.info(f"Updated stop loss for position {ticket} from {current_sl:.2f} to {new_sl:.2f}")
                                
                                # Add result
                                modify_result = {
                                    "symbol": symbol,
                                    "ticket": ticket,
                                    "action": "modify",
                                    "new_sl": new_sl,
                                    "time": datetime.now(),
                                    "type": "modify_position",
                                    "reason": "Adjusted stop loss based on price progress toward VWAP"
                                }
                                
                                results.append(modify_result)
                
            except Exception as e:
                self.logger.error(f"Error managing position: {str(e)}")
                
        return results
    
    def manage_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply VWAP-specific risk management rules to the signals.
        
        Args:
            signals: List of signals to risk-manage
            
        Returns:
            List[Dict]: Risk-adjusted signals
        """
        # First apply the day trading risk management
        signals = super().manage_risk(signals)
        
        risk_adjusted_signals = []
        
        for signal in signals:
            symbol = signal.get("symbol", "")
            
            # Verify the signal is still valid (price hasn't moved significantly)
            if symbol in self.vwap_data:
                vwap_info = self.vwap_data[symbol]
                current_price = vwap_info.get("current_price", 0)
                signal_price = signal.get("price", 0)
                
                # Skip if price has moved too much from signal generation
                price_diff_pct = abs(current_price - signal_price) / signal_price * 100
                
                if price_diff_pct > 0.2:  # 0.2% threshold
                    self.logger.info(f"Skipping {symbol} signal, price moved {price_diff_pct:.2f}% since signal generation")
                    continue
                
                # Ensure the signal direction still makes sense relative to VWAP
                action = signal.get("action", "")
                vwap = vwap_info.get("vwap", 0)
                
                if (action == "buy" and current_price > vwap) or (action == "sell" and current_price < vwap):
                    self.logger.info(f"Skipping {symbol} {action} signal, price has already crossed VWAP")
                    continue
            
            risk_adjusted_signals.append(signal)
        
        return risk_adjusted_signals 