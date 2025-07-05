#!/usr/bin/env python3
"""
Base class for day trading strategies.
These strategies focus on intraday price movements and typically close all positions by the end of the trading day.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, time, timedelta
import pytz
import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy
from src.utils.logger import setup_logger

class DayStrategyBase(BaseStrategy):
    """Base class for day trading strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the day trading strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__(config)
        self.logger = setup_logger(f"{self.__class__.__name__}", f"logs/strategies/{self.__class__.__name__}.log")
        
        # Day trading specific configuration
        self.max_daily_trades = config.get("max_daily_trades", 5)
        self.max_daily_drawdown = config.get("max_daily_drawdown", 3.0)  # percentage
        self.profit_target = config.get("profit_target", 2.0)  # percentage
        self.trading_hours = config.get("trading_hours", {
            "start": "09:30",
            "end": "16:00",
            "timezone": "America/New_York"
        })
        
        # Convert trading hours to time objects
        self.market_open = datetime.strptime(self.trading_hours["start"], "%H:%M").time()
        self.market_close = datetime.strptime(self.trading_hours["end"], "%H:%M").time()
        self.market_timezone = pytz.timezone(self.trading_hours["timezone"])
        
        # Day tracking
        self.current_day = None
        self.day_stats = {}
        self.daily_trades = []
        self.daily_pnl = 0.0
        self.max_daily_capital = config.get("max_daily_capital", 100000.0)
        self.remaining_daily_capital = self.max_daily_capital
        self.open_positions = []
        
    def initialize(self) -> bool:
        """
        Initialize the day trading strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing day trading strategy: {self.__class__.__name__}")
        self._reset_daily_stats()
        return True
        
    def _reset_daily_stats(self) -> None:
        """Reset daily statistics at the start of a new trading day."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        self.daily_trades = []
        self.daily_pnl = 0.0
        self.remaining_daily_capital = self.max_daily_capital
        
        self.day_stats = {
            "date": today,
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "profit": 0.0,
            "loss": 0.0,
            "max_drawdown": 0.0,
            "start_time": None,
            "end_time": None,
            "closed_positions": []
        }
        
    def is_market_open(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if the market is currently open.
        
        Args:
            current_time: Current time (defaults to now)
            
        Returns:
            bool: True if the market is open, False otherwise
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
            
        # Convert to market timezone
        market_time = current_time.astimezone(self.market_timezone)
        
        # Check if it's a weekday (0 = Monday, 6 = Sunday)
        if market_time.weekday() >= 5:  # Saturday or Sunday
            return False
            
        # Check if within trading hours
        current_market_time = market_time.time()
        return self.market_open <= current_market_time < self.market_close
        
    def time_to_market_open(self, current_time: Optional[datetime] = None) -> float:
        """
        Calculate time until market open in minutes.
        
        Args:
            current_time: Current time (defaults to now)
            
        Returns:
            float: Minutes until market open, 0 if market is open, -1 if market is closed for the day
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
            
        # Convert to market timezone
        market_time = current_time.astimezone(self.market_timezone)
        
        # Check if it's a weekday
        if market_time.weekday() >= 5:  # Saturday or Sunday
            # Calculate days until Monday
            days_to_monday = (7 - market_time.weekday()) % 7
            if days_to_monday == 0:
                days_to_monday = 1
                
            # Return minutes until Monday market open
            next_market_open = datetime.combine(
                (market_time + timedelta(days=days_to_monday)).date(),
                self.market_open
            )
            next_market_open = self.market_timezone.localize(next_market_open)
            
            return (next_market_open - market_time).total_seconds() / 60
            
        # If today is a weekday
        current_market_time = market_time.time()
        
        # If before market open today
        if current_market_time < self.market_open:
            next_market_open = datetime.combine(market_time.date(), self.market_open)
            next_market_open = self.market_timezone.localize(next_market_open)
            return (next_market_open - market_time).total_seconds() / 60
            
        # If after market close today
        if current_market_time >= self.market_close:
            # Calculate time until tomorrow's market open
            next_day = market_time.date() + timedelta(days=1)
            
            # If tomorrow is a weekend, calculate days until Monday
            if next_day.weekday() >= 5:
                days_to_monday = (7 - next_day.weekday()) % 7
                next_day = next_day + timedelta(days=days_to_monday)
                
            next_market_open = datetime.combine(next_day, self.market_open)
            next_market_open = self.market_timezone.localize(next_market_open)
            return (next_market_open - market_time).total_seconds() / 60
            
        # If market is open
        return 0
        
    def time_to_market_close(self, current_time: Optional[datetime] = None) -> float:
        """
        Calculate time until market close in minutes.
        
        Args:
            current_time: Current time (defaults to now)
            
        Returns:
            float: Minutes until market close, -1 if market is closed
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
            
        # Convert to market timezone
        market_time = current_time.astimezone(self.market_timezone)
        current_market_time = market_time.time()
        
        # If not a weekday or outside trading hours, market is closed
        if market_time.weekday() >= 5 or current_market_time < self.market_open or current_market_time >= self.market_close:
            return -1
            
        # Calculate time until market close
        market_close_today = datetime.combine(market_time.date(), self.market_close)
        market_close_today = self.market_timezone.localize(market_close_today)
        
        return (market_close_today - market_time).total_seconds() / 60
        
    def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze the market conditions for day trading.
        
        Returns:
            Dict: Analysis results
        """
        current_time = datetime.now(pytz.UTC)
        market_time = current_time.astimezone(self.market_timezone)
        today = market_time.strftime("%Y-%m-%d")
        
        # Check if it's a new trading day
        if self.current_day != today:
            self.logger.info(f"New trading day: {today}")
            self._reset_daily_stats()
            self.current_day = today
            
            if self.is_market_open(current_time):
                self.day_stats["start_time"] = market_time
        
        # Check market status
        is_open = self.is_market_open(current_time)
        time_to_open = self.time_to_market_open(current_time)
        time_to_close = self.time_to_market_close(current_time)
        
        # Update end time if market is closing
        if not is_open and self.day_stats["start_time"] is not None and self.day_stats["end_time"] is None:
            self.day_stats["end_time"] = market_time
            self.logger.info(f"Market closed for the day. Daily P&L: {self.daily_pnl:.2f}")
            
            # Close any remaining positions
            if self.open_positions:
                self.logger.info(f"Closing {len(self.open_positions)} remaining positions at market close")
                self._close_all_positions()
        
        # Return analysis results
        return {
            "date": today,
            "market_time": market_time,
            "is_open": is_open,
            "time_to_open": time_to_open,
            "time_to_close": time_to_close,
            "daily_trades": len(self.daily_trades),
            "max_daily_trades": self.max_daily_trades,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_percentage": (self.daily_pnl / self.max_daily_capital) * 100 if self.max_daily_capital > 0 else 0,
            "remaining_daily_capital": self.remaining_daily_capital,
            "open_positions": len(self.open_positions)
        }
        
    def _close_all_positions(self) -> List[Dict[str, Any]]:
        """
        Close all open positions.
        
        Returns:
            List[Dict]: Results of the closing operations
        """
        # This should be implemented by subclasses
        return []
        
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals for day trading.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        current_time = datetime.now(pytz.UTC)
        
        # Only generate signals if market is open and we haven't reached max trades
        if not self.is_market_open(current_time) or len(self.daily_trades) >= self.max_daily_trades:
            return []
            
        # Check if we've hit our profit target or max drawdown
        daily_pnl_percentage = (self.daily_pnl / self.max_daily_capital) * 100 if self.max_daily_capital > 0 else 0
        
        if daily_pnl_percentage <= -self.max_daily_drawdown:
            self.logger.info(f"Reached max daily drawdown: {daily_pnl_percentage:.2f}%. Stopping for the day.")
            return []
            
        if daily_pnl_percentage >= self.profit_target:
            self.logger.info(f"Reached daily profit target: {daily_pnl_percentage:.2f}%. Stopping for the day.")
            return []
            
        # Time to market close in minutes
        time_to_close = self.time_to_market_close(current_time)
        
        # If less than 15 minutes to market close, don't open new positions
        if 0 < time_to_close < 15:
            self.logger.info(f"Less than 15 minutes to market close ({time_to_close:.2f} min). Not opening new positions.")
            return []
            
        # This should be implemented by subclasses
        return []
        
    def manage_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply day trading specific risk management rules to the signals.
        
        Args:
            signals: List of signals to risk-manage
            
        Returns:
            List[Dict]: Risk-adjusted signals
        """
        if not signals:
            return []
            
        risk_adjusted_signals = []
        
        for signal in signals:
            # Skip if we've hit max trades for the day
            if len(self.daily_trades) >= self.max_daily_trades:
                continue
                
            # Calculate position size based on remaining daily capital
            estimated_size = signal.get("size", 0)
            symbol = signal.get("symbol", "")
            price = signal.get("price", 0)
            
            if price <= 0 or estimated_size <= 0:
                continue
                
            position_value = price * estimated_size
            
            # Adjust position size if it exceeds remaining daily capital
            if position_value > self.remaining_daily_capital:
                adjusted_size = int(self.remaining_daily_capital / price)
                if adjusted_size <= 0:
                    continue
                    
                self.logger.info(f"Adjusted position size for {symbol} from {estimated_size} to {adjusted_size}")
                signal["size"] = adjusted_size
                position_value = price * adjusted_size
                
            # Reserve the capital for this position
            self.remaining_daily_capital -= position_value
            
            risk_adjusted_signals.append(signal)
            
        return risk_adjusted_signals
        
    def update_stats(self, trade_results: List[Dict[str, Any]]) -> None:
        """
        Update day trading statistics based on trade results.
        
        Args:
            trade_results: Results of executed trades
        """
        super().update_stats(trade_results)
        
        for result in trade_results:
            # Skip if not a new trade
            if result.get("type") != "new_position":
                continue
                
            # Add to daily trades
            self.daily_trades.append(result)
            self.day_stats["trades"] += 1
            
            # Add to open positions
            self.open_positions.append(result)
            
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage existing positions (apply trailing stops, take profits, etc.)
        
        Returns:
            List[Dict]: Results of position management actions
        """
        current_time = datetime.now(pytz.UTC)
        
        # If market is closing soon (< 5 minutes), close all positions
        time_to_close = self.time_to_market_close(current_time)
        if 0 < time_to_close < 5 and self.open_positions:
            self.logger.info(f"Market closing in {time_to_close:.2f} minutes. Closing all positions.")
            return self._close_all_positions()
            
        # This should be implemented by subclasses
        return [] 