#!/usr/bin/env python3
"""
London Breakout Strategy

This strategy trades the volatility breakout that often occurs at the start of the London trading session.
It identifies the price range during the pre-London hours and places orders to catch the breakout when London opens.
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np

from src.strategies.session_based.session_strategy_base import SessionStrategyBase
from src.brokers.mt5_connector import MT5Connector
from src.utils.logger import setup_logger

class LondonBreakoutStrategy(SessionStrategyBase):
    """
    A strategy that trades the volatility breakout at the start of the London session.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the London breakout strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        # Default to London session only
        if "target_sessions" not in config:
            config["target_sessions"] = ["london"]
            
        super().__init__(config)
        
        # Strategy-specific configuration
        self.symbols = config.get("symbols", ["EURUSD", "GBPUSD", "USDJPY", "EURGBP"])
        self.range_hours = config.get("range_hours", 3)  # Hours before London open to calculate range
        self.breakout_trigger = config.get("breakout_trigger", 0.5)  # Percentage of range to trigger entry
        self.stop_loss_factor = config.get("stop_loss_factor", 1.0)  # Multiple of range for stop loss
        self.take_profit_factor = config.get("take_profit_factor", 2.0)  # Multiple of range for take profit
        self.max_spread_pips = config.get("max_spread_pips", 1.5)  # Maximum spread in pips
        self.max_trade_duration = config.get("max_trade_duration", 6)  # Hours to keep trade open
        
        # Trade management
        self.pending_orders = {}
        self.open_trades = {}
        self.range_data = {}
        
        # Broker connection
        self.broker = None
        self.mt5_config_path = config.get("mt5_config_path", "config/brokers/mt5_config.json")
        
    def initialize(self) -> bool:
        """
        Initialize the London breakout strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing London breakout strategy")
        
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
        
    def _on_session_start(self, session_name: str) -> None:
        """
        Handle session start event. For London session, calculate the pre-session range
        and place breakout orders.
        
        Args:
            session_name: Name of the session that is starting
        """
        super()._on_session_start(session_name)
        
        if session_name == "london":
            self.logger.info("London session starting, calculating pre-session ranges")
            
            # Calculate pre-session range for each symbol
            self._calculate_pre_london_ranges()
            
            # Place breakout orders
            self._place_breakout_orders()
    
    def _on_session_end(self, session_name: str) -> None:
        """
        Handle session end event. For London session, cancel any pending orders
        and evaluate the session's performance.
        
        Args:
            session_name: Name of the session that is ending
        """
        if session_name == "london":
            self.logger.info("London session ending, cancelling pending orders")
            
            # Cancel any pending orders
            self._cancel_pending_orders()
            
        super()._on_session_end(session_name)
    
    def _calculate_pre_london_ranges(self) -> None:
        """Calculate the price ranges for each symbol before London session opens."""
        now = datetime.now(pytz.UTC)
        london_session = self.SESSIONS["london"]
        
        # Calculate the start of the range period
        range_start = now.replace(
            hour=london_session["start"].hour - self.range_hours,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if range_start.hour < 0:
            # Handle case where range starts the previous day
            range_start = range_start.replace(hour=range_start.hour + 24) - timedelta(days=1)
        
        # Calculate the end of the range period (London open)
        range_end = now.replace(
            hour=london_session["start"].hour,
            minute=london_session["start"].minute,
            second=0,
            microsecond=0
        )
        
        self.logger.info(f"Calculating pre-London range from {range_start.strftime('%H:%M')} to {range_end.strftime('%H:%M')} UTC")
        
        # Get data for each symbol
        for symbol in self.symbols:
            try:
                if not self.broker:
                    continue
                    
                # Get historical data
                timeframe = "M15"  # 15-minute timeframe
                data = self.broker.get_historical_data(
                    symbol, 
                    timeframe, 
                    int((range_end - range_start).total_seconds() / 60 / 15) + 5  # Add buffer
                )
                
                if data is None or data.empty:
                    self.logger.warning(f"No data available for {symbol}")
                    continue
                    
                # Filter data to the range period
                data['datetime'] = pd.to_datetime(data['time'])
                range_data = data[
                    (data['datetime'] >= range_start) & 
                    (data['datetime'] < range_end)
                ]
                
                if range_data.empty:
                    self.logger.warning(f"No data in range period for {symbol}")
                    continue
                
                # Calculate the high and low of the range
                range_high = range_data['high'].max()
                range_low = range_data['low'].min()
                range_size = range_high - range_low
                
                # Store the range data
                self.range_data[symbol] = {
                    "high": range_high,
                    "low": range_low,
                    "size": range_size,
                    "mid": (range_high + range_low) / 2,
                    "calculated_at": now
                }
                
                self.logger.info(f"{symbol} range: High={range_high:.5f}, Low={range_low:.5f}, Size={range_size:.5f} pips")
                
            except Exception as e:
                self.logger.error(f"Error calculating range for {symbol}: {str(e)}")
    
    def _place_breakout_orders(self) -> None:
        """Place breakout orders for symbols with valid range data."""
        for symbol, range_info in self.range_data.items():
            try:
                if not self.broker:
                    continue
                    
                # Check if range is valid
                if range_info["size"] <= 0:
                    self.logger.warning(f"Invalid range size for {symbol}: {range_info['size']}")
                    continue
                
                # Get current price
                current_price = self.broker.get_current_price(symbol)
                if not current_price:
                    self.logger.warning(f"Could not get current price for {symbol}")
                    continue
                    
                # Get symbol info for pip value and spread
                symbol_info = self.broker.get_symbol_info(symbol)
                if not symbol_info:
                    self.logger.warning(f"Could not get symbol info for {symbol}")
                    continue
                    
                # Check if spread is acceptable
                current_spread = symbol_info.spread * self.broker.point
                max_spread = self.max_spread_pips * (0.0001 if symbol.endswith("JPY") else 0.00001)
                
                if current_spread > max_spread:
                    self.logger.warning(f"Spread too high for {symbol}: {current_spread:.5f} > {max_spread:.5f}")
                    continue
                
                # Calculate entry points
                buy_entry = range_info["high"] + (range_info["size"] * self.breakout_trigger)
                sell_entry = range_info["low"] - (range_info["size"] * self.breakout_trigger)
                
                # Calculate stop loss and take profit levels
                buy_sl = buy_entry - (range_info["size"] * self.stop_loss_factor)
                buy_tp = buy_entry + (range_info["size"] * self.take_profit_factor)
                
                sell_sl = sell_entry + (range_info["size"] * self.stop_loss_factor)
                sell_tp = sell_entry - (range_info["size"] * self.take_profit_factor)
                
                # Calculate position size
                account_info = self.broker.get_account_info()
                risk_amount = account_info["balance"] * (self.risk_per_trade / 100)
                
                # Calculate pips at risk
                buy_risk_pips = (buy_entry - buy_sl) / self.broker.point
                sell_risk_pips = (sell_sl - sell_entry) / self.broker.point
                
                # Calculate position size
                pip_value = self.broker.get_pip_value(symbol)
                
                if pip_value > 0:
                    buy_size = risk_amount / (buy_risk_pips * pip_value)
                    sell_size = risk_amount / (sell_risk_pips * pip_value)
                    
                    # Round to standard lot size
                    lot_step = symbol_info.volume_step
                    buy_size = max(round(buy_size / lot_step) * lot_step, lot_step)
                    sell_size = max(round(sell_size / lot_step) * lot_step, lot_step)
                else:
                    # Default to minimum position size
                    buy_size = sell_size = 0.01
                
                # Place pending orders
                expiration = datetime.now() + timedelta(hours=self.max_trade_duration)
                
                # Buy stop order
                buy_ticket = self.broker.place_pending_order(
                    symbol, 
                    "buy_stop", 
                    buy_size, 
                    buy_entry, 
                    buy_sl, 
                    buy_tp, 
                    expiration
                )
                
                # Sell stop order
                sell_ticket = self.broker.place_pending_order(
                    symbol, 
                    "sell_stop", 
                    sell_size, 
                    sell_entry, 
                    sell_sl, 
                    sell_tp, 
                    expiration
                )
                
                # Store pending orders
                if buy_ticket:
                    self.pending_orders[buy_ticket] = {
                        "symbol": symbol,
                        "type": "buy_stop",
                        "price": buy_entry,
                        "size": buy_size,
                        "sl": buy_sl,
                        "tp": buy_tp,
                        "placed_at": datetime.now(),
                        "expiration": expiration
                    }
                    
                    self.logger.info(f"Placed buy stop order for {symbol} at {buy_entry:.5f}, size: {buy_size}, SL: {buy_sl:.5f}, TP: {buy_tp:.5f}")
                
                if sell_ticket:
                    self.pending_orders[sell_ticket] = {
                        "symbol": symbol,
                        "type": "sell_stop",
                        "price": sell_entry,
                        "size": sell_size,
                        "sl": sell_sl,
                        "tp": sell_tp,
                        "placed_at": datetime.now(),
                        "expiration": expiration
                    }
                    
                    self.logger.info(f"Placed sell stop order for {symbol} at {sell_entry:.5f}, size: {sell_size}, SL: {sell_sl:.5f}, TP: {sell_tp:.5f}")
                
            except Exception as e:
                self.logger.error(f"Error placing breakout orders for {symbol}: {str(e)}")
    
    def _cancel_pending_orders(self) -> None:
        """Cancel all pending breakout orders."""
        if not self.broker:
            return
            
        for ticket, order_info in list(self.pending_orders.items()):
            try:
                result = self.broker.cancel_order(ticket)
                
                if result:
                    self.logger.info(f"Cancelled pending order {ticket} for {order_info['symbol']}")
                    del self.pending_orders[ticket]
                else:
                    self.logger.warning(f"Failed to cancel pending order {ticket}")
                    
            except Exception as e:
                self.logger.error(f"Error cancelling order {ticket}: {str(e)}")
    
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on the strategy logic.
        During London session, we rely on pending orders rather than generating new signals.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        # During London session, we rely on pending orders
        if self.in_active_session and self.current_session == "london":
            return []
            
        # If outside London session and approaching the start, prepare for the breakout
        analysis = self.analyze_market()
        next_session = analysis.get("next_session", None)
        
        if next_session and next_session["name"] == "london" and next_session["time_until"] <= 30:
            self.logger.info(f"London session starting in {next_session['time_until']:.1f} minutes, preparing for breakout")
            
            # Calculate pre-session ranges if not already done
            if not self.range_data:
                self._calculate_pre_london_ranges()
        
        return []
    
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage existing positions by monitoring and adjusting stops.
        
        Returns:
            List[Dict]: Results of position management actions
        """
        results = []
        
        if not self.broker:
            return results
            
        # Get all open positions
        open_positions = self.broker.get_open_positions()
        
        for position in open_positions:
            try:
                symbol = position.get("symbol", "")
                ticket = position.get("ticket", 0)
                open_time = position.get("time", datetime.now())
                current_profit = position.get("profit", 0)
                
                # Check if the position has been open for too long
                position_age = (datetime.now() - open_time).total_seconds() / 3600  # hours
                
                # If position has been open longer than the max duration, close it
                if position_age >= self.max_trade_duration:
                    result = self.broker.close_position(ticket)
                    
                    if result:
                        self.logger.info(f"Closed position {ticket} after {position_age:.1f} hours, profit: {current_profit:.2f}")
                        
                        # Add result
                        close_result = {
                            "symbol": symbol,
                            "ticket": ticket,
                            "action": "close",
                            "profit": current_profit,
                            "time": datetime.now(),
                            "type": "close_position",
                            "reason": f"Max trade duration ({self.max_trade_duration} hours) elapsed"
                        }
                        
                        results.append(close_result)
                
                # Implement trailing stop if in profit
                if current_profit > 0 and symbol in self.range_data:
                    range_size = self.range_data[symbol]["size"]
                    
                    # If profit is at least 1x range size, move stop to breakeven
                    if current_profit >= range_size and position.get("sl", 0) != position.get("open_price", 0):
                        new_sl = position.get("open_price", 0)
                        
                        result = self.broker.modify_position(ticket, new_sl, position.get("tp", 0))
                        
                        if result:
                            self.logger.info(f"Moved stop loss to breakeven for position {ticket}, profit: {current_profit:.2f}")
                            
                            # Add result
                            modify_result = {
                                "symbol": symbol,
                                "ticket": ticket,
                                "action": "modify",
                                "new_sl": new_sl,
                                "time": datetime.now(),
                                "type": "modify_position",
                                "reason": "Moved stop to breakeven"
                            }
                            
                            results.append(modify_result)
                
            except Exception as e:
                self.logger.error(f"Error managing position: {str(e)}")
                
        return results
    
    def manage_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply session-specific risk management rules to the signals.
        
        Args:
            signals: List of signals to risk-manage
            
        Returns:
            List[Dict]: Risk-adjusted signals
        """
        # London breakout strategy uses pending orders, so this is less relevant
        return signals
    
    def execute_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute the generated signals by placing orders with the broker.
        
        Args:
            signals: List of signals to execute
            
        Returns:
            List[Dict]: Results of the execution attempts
        """
        # London breakout strategy uses pending orders, so this is less relevant
        return [] 