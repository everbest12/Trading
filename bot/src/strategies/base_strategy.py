#!/usr/bin/env python3
"""
Base strategy class that all other strategies will inherit from.
Provides common functionality and interfaces for all trading strategies.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the base strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        self.config = config
        self.symbol = config.get("symbol", "")
        self.timeframe = config.get("timeframe", "")
        self.is_running = False
        self.last_run_time = None
        self.trades = []
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_profit": 0.0,
            "total_loss": 0.0
        }
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the strategy, connect to brokers, and set up data streams.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        pass
        
    @abstractmethod
    def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze the market conditions and prepare for signal generation.
        
        Returns:
            Dict: Analysis results
        """
        pass
    
    @abstractmethod
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on the strategy logic.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        pass
    
    @abstractmethod
    def execute_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute the generated signals by placing orders with the broker.
        
        Args:
            signals: List of signals to execute
            
        Returns:
            List[Dict]: Results of the execution attempts
        """
        pass
    
    @abstractmethod
    def manage_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply risk management rules to the signals before execution.
        
        Args:
            signals: List of signals to risk-manage
            
        Returns:
            List[Dict]: Risk-adjusted signals
        """
        pass
    
    @abstractmethod
    def manage_positions(self) -> List[Dict[str, Any]]:
        """
        Manage existing positions (apply trailing stops, take profits, etc.)
        
        Returns:
            List[Dict]: Results of position management actions
        """
        pass
    
    def update_stats(self, trade_results: List[Dict[str, Any]]) -> None:
        """
        Update strategy statistics based on trade results.
        
        Args:
            trade_results: Results of executed trades
        """
        for result in trade_results:
            self.stats["total_trades"] += 1
            
            if result.get("profit", 0) > 0:
                self.stats["winning_trades"] += 1
                self.stats["total_profit"] += result.get("profit", 0)
            else:
                self.stats["losing_trades"] += 1
                self.stats["total_loss"] += abs(result.get("profit", 0))
                
            self.trades.append({
                "timestamp": datetime.now(),
                "action": result.get("action", ""),
                "symbol": result.get("symbol", ""),
                "price": result.get("price", 0),
                "size": result.get("size", 0),
                "profit": result.get("profit", 0)
            })
    
    def run(self, iterations: Optional[int] = None) -> None:
        """
        Run the strategy for a specified number of iterations or indefinitely.
        
        Args:
            iterations: Number of iterations to run, or None for indefinite running
        """
        self.is_running = True
        iteration_count = 0
        
        if not self.initialize():
            self.is_running = False
            return
        
        try:
            while self.is_running:
                self.last_run_time = datetime.now()
                
                # Strategy execution flow
                analysis = self.analyze_market()
                signals = self.generate_signals()
                risk_adjusted_signals = self.manage_risk(signals)
                execution_results = self.execute_signals(risk_adjusted_signals)
                position_management_results = self.manage_positions()
                
                # Update strategy statistics
                self.update_stats(execution_results)
                
                # Check if we've reached the maximum iterations
                iteration_count += 1
                if iterations is not None and iteration_count >= iterations:
                    break
                    
                # Throttle execution rate
                time.sleep(self.config.get("execution_interval", 1))
                
        except Exception as e:
            print(f"Error running strategy: {str(e)}")
        finally:
            self.is_running = False
            
    def stop(self) -> None:
        """Stop the strategy execution."""
        self.is_running = False
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get the current statistics for the strategy.
        
        Returns:
            Dict: Strategy statistics
        """
        win_rate = 0
        if self.stats["total_trades"] > 0:
            win_rate = self.stats["winning_trades"] / self.stats["total_trades"] * 100
            
        return {
            **self.stats,
            "win_rate": win_rate,
            "net_profit": self.stats["total_profit"] - self.stats["total_loss"],
            "last_run_time": self.last_run_time
        } 