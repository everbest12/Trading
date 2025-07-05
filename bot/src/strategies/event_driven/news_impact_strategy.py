#!/usr/bin/env python3
"""
News Impact Strategy

This strategy monitors news feeds and financial calendars for market-moving events
and places trades based on the expected market impact of these events.
"""

import re
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np
from loguru import logger

from src.strategies.event_driven.event_strategy_base import EventStrategyBase
from src.brokers.mt5_connector import MT5Connector
from src.utils.logger import setup_logger

class NewsImpactStrategy(EventStrategyBase):
    """
    A strategy that trades based on the impact of economic news releases and events.
    """
    
    # News impact classification
    IMPACT_LEVELS = {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    }
    
    # Currency to symbols mapping (for forex)
    CURRENCY_SYMBOLS = {
        "USD": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"],
        "EUR": ["EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD"],
        "GBP": ["GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD"],
        "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY"],
        "AUD": ["AUDUSD", "EURAUD", "GBPAUD", "AUDJPY", "AUDCAD", "AUDCHF", "AUDNZD"],
        "CAD": ["USDCAD", "EURCAD", "GBPCAD", "CADJPY", "AUDCAD", "CADCHF"],
        "CHF": ["USDCHF", "EURCHF", "GBPCHF", "CHFJPY", "AUDCHF", "CADCHF"],
        "NZD": ["NZDUSD", "EURNZD", "GBPNZD", "NZDJPY", "AUDNZD", "NZDCAD", "NZDCHF"]
    }
    
    # News categories to event types mapping
    NEWS_CATEGORIES = {
        "interest_rate": ["rate decision", "interest rate", "fed", "fomc", "boe", "ecb", "rba", "boj"],
        "employment": ["nonfarm payroll", "unemployment", "employment", "jobless claims", "jobs"],
        "inflation": ["cpi", "inflation", "ppi", "price index", "consumer price"],
        "gdp": ["gdp", "economic growth", "gross domestic product"],
        "retail": ["retail sales", "consumer spending", "consumption"],
        "manufacturing": ["pmi", "manufacturing", "industrial production", "factory"],
        "housing": ["housing", "home sales", "building permits", "construction"],
        "trade": ["trade balance", "export", "import", "trade deficit"]
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the news impact strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__(config)
        
        # News-specific configuration
        self.impact_threshold = config.get("impact_threshold", 0.7)  # Only trade high-impact news by default
        self.pre_news_buffer = config.get("pre_news_buffer", 5)  # Minutes before news to avoid trading
        self.post_news_reaction = config.get("post_news_reaction", 1)  # Minutes after news before trading
        self.position_hold_time = config.get("position_hold_time", 15)  # Minutes to hold position
        self.news_volatility_factor = config.get("news_volatility_factor", 1.5)  # Multiplier for volatility-based stop loss
        
        # Trading parameters
        self.risk_per_trade = config.get("risk_per_trade", 1.0)  # Percentage of account to risk per trade
        self.target_profit_ratio = config.get("target_profit_ratio", 2.0)  # Risk-reward ratio
        self.max_spread_factor = config.get("max_spread_factor", 1.5)  # Maximum spread as multiple of average
        
        # Market data
        self.avg_spreads = {}
        self.avg_volatility = {}
        self.news_calendar = pd.DataFrame()
        self.last_calendar_update = None
        self.calendar_update_interval = config.get("calendar_update_interval", 3600)  # Seconds
        
        # Broker connection
        self.broker = None
        self.mt5_config_path = config.get("mt5_config_path", "config/brokers/mt5_config.json")
        
    def initialize(self) -> bool:
        """
        Initialize the news impact strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info("Initializing news impact strategy")
        
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
            
        # Load historical volatility and spreads
        self._load_market_data()
        
        # Load economic calendar
        self._update_economic_calendar()
        
        # Initialize event monitoring
        result = super().initialize()
        
        return result
        
    def _load_market_data(self) -> None:
        """Load historical market data for volatility calculation."""
        self.logger.info("Loading market data for volatility analysis")
        
        for currency, symbols in self.CURRENCY_SYMBOLS.items():
            for symbol in symbols:
                try:
                    # Get historical data
                    if self.broker:
                        df = self.broker.get_historical_data(symbol, "H1", 100)
                        
                        if df is not None and not df.empty:
                            # Calculate average volatility (high-low range)
                            volatility = (df['high'] - df['low']).mean()
                            self.avg_volatility[symbol] = volatility
                            
                            # Calculate average spread
                            if hasattr(self.broker, 'get_symbol_info'):
                                symbol_info = self.broker.get_symbol_info(symbol)
                                if symbol_info:
                                    self.avg_spreads[symbol] = symbol_info.spread * self.broker.point
                                
                            self.logger.info(f"Loaded data for {symbol}: Volatility = {volatility:.5f}")
                except Exception as e:
                    self.logger.error(f"Error loading data for {symbol}: {str(e)}")
        
    def _update_economic_calendar(self) -> None:
        """Update the economic calendar data."""
        now = datetime.now()
        
        # Only update if it's been more than the update interval since last update
        if (self.last_calendar_update is None or 
                (now - self.last_calendar_update).total_seconds() > self.calendar_update_interval):
            
            self.logger.info("Updating economic calendar")
            
            # TODO: Implement actual economic calendar API call
            # For now, we'll create a sample calendar
            self._create_sample_calendar()
            
            self.last_calendar_update = now
    
    def _create_sample_calendar(self) -> None:
        """Create a sample economic calendar for testing."""
        now = datetime.now()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
        
        # Sample news events
        events = [
            {
                "datetime": start_date + timedelta(minutes=30),
                "country": "US",
                "currency": "USD",
                "event": "Non-Farm Payrolls",
                "impact": "high",
                "forecast": "200K",
                "previous": "180K"
            },
            {
                "datetime": start_date + timedelta(hours=3),
                "country": "EU",
                "currency": "EUR",
                "event": "ECB Interest Rate Decision",
                "impact": "high",
                "forecast": "3.75%",
                "previous": "3.75%"
            },
            {
                "datetime": start_date + timedelta(hours=5),
                "country": "UK",
                "currency": "GBP",
                "event": "GDP Growth Rate QoQ",
                "impact": "medium",
                "forecast": "0.2%",
                "previous": "0.1%"
            },
            {
                "datetime": start_date + timedelta(days=1, hours=1),
                "country": "US",
                "currency": "USD",
                "event": "CPI YoY",
                "impact": "high",
                "forecast": "3.2%",
                "previous": "3.3%"
            },
            {
                "datetime": start_date + timedelta(days=1, hours=10),
                "country": "JP",
                "currency": "JPY",
                "event": "BOJ Outlook Report",
                "impact": "medium",
                "forecast": "",
                "previous": ""
            }
        ]
        
        # Create DataFrame
        self.news_calendar = pd.DataFrame(events)
        
        # Add derived information
        if not self.news_calendar.empty:
            self.news_calendar["time_until"] = self.news_calendar["datetime"].apply(
                lambda x: (x - datetime.now()).total_seconds() / 60
            )
            
            # Categorize events
            self.news_calendar["category"] = self.news_calendar["event"].apply(self._categorize_event)
            
            # Convert impact to numeric
            self.news_calendar["impact_value"] = self.news_calendar["impact"].apply(
                lambda x: self.IMPACT_LEVELS.get(x.lower(), 0) if isinstance(x, str) else 0
            )
            
            self.logger.info(f"Created sample calendar with {len(events)} events")
    
    def _categorize_event(self, event_name: str) -> str:
        """
        Categorize an event based on its name.
        
        Args:
            event_name: Name of the event
            
        Returns:
            str: Category of the event
        """
        if not isinstance(event_name, str):
            return "other"
            
        event_lower = event_name.lower()
        
        for category, keywords in self.NEWS_CATEGORIES.items():
            for keyword in keywords:
                if keyword in event_lower:
                    return category
                    
        return "other"
    
    def _poll_event_source(self, source: str) -> List[Dict[str, Any]]:
        """
        Poll an event source for new events.
        
        Args:
            source: Name of the event source
            
        Returns:
            List[Dict]: List of event dictionaries
        """
        if source == "economic_calendar":
            # Update the calendar if needed
            self._update_economic_calendar()
            
            # Look for upcoming events
            upcoming_events = []
            
            if not self.news_calendar.empty:
                # Filter events occurring soon (within next 30 minutes)
                soon = self.news_calendar[
                    (self.news_calendar["time_until"] <= 30) & 
                    (self.news_calendar["time_until"] > 0)
                ]
                
                # Convert to event dictionaries
                for _, row in soon.iterrows():
                    event = {
                        "type": "economic_release",
                        "source": "economic_calendar",
                        "timestamp": row["datetime"],
                        "country": row["country"],
                        "currency": row["currency"],
                        "event": row["event"],
                        "category": row.get("category", "other"),
                        "importance": row.get("impact_value", 0),
                        "forecast": row.get("forecast", ""),
                        "previous": row.get("previous", ""),
                        "time_until_minutes": row.get("time_until", 0)
                    }
                    upcoming_events.append(event)
                    
            return upcoming_events
            
        # Add other event sources as needed
        return []
    
    def _react_to_event(self, event: Dict[str, Any]) -> None:
        """
        React to an event by generating signals.
        
        Args:
            event: Event dictionary
        """
        event_type = event.get("type", "")
        
        if event_type == "economic_release":
            self._react_to_economic_release(event)
    
    def _react_to_economic_release(self, event: Dict[str, Any]) -> None:
        """
        React to an economic release event.
        
        Args:
            event: Economic release event dictionary
        """
        currency = event.get("currency", "")
        importance = event.get("importance", 0)
        time_until = event.get("time_until_minutes", 0)
        event_name = event.get("event", "")
        
        self.logger.info(f"Processing economic release: {event_name} ({currency}), importance: {importance:.2f}, time until: {time_until:.1f} min")
        
        # If the event is high-impact and about to happen, close existing positions on affected symbols
        if importance >= self.impact_threshold and time_until <= self.pre_news_buffer:
            affected_symbols = self._get_affected_symbols(currency)
            
            if affected_symbols:
                self.logger.info(f"High-impact event approaching. Closing positions for: {', '.join(affected_symbols)}")
                self._close_positions_for_symbols(affected_symbols)
        
        # If the event just happened and is high-impact, generate trading signals
        if importance >= self.impact_threshold and 0 <= time_until <= self.post_news_reaction:
            self.logger.info(f"High-impact event just released. Generating trading signals.")
            self._generate_post_news_signals(event)
    
    def _get_affected_symbols(self, currency: str) -> List[str]:
        """
        Get the symbols affected by news for a specific currency.
        
        Args:
            currency: Currency code
            
        Returns:
            List[str]: List of affected symbols
        """
        return self.CURRENCY_SYMBOLS.get(currency, [])
    
    def _close_positions_for_symbols(self, symbols: List[str]) -> None:
        """
        Close all open positions for specific symbols.
        
        Args:
            symbols: List of symbols to close positions for
        """
        if not self.broker:
            return
            
        for symbol in symbols:
            try:
                self.broker.close_positions_by_symbol(symbol)
                self.logger.info(f"Closed positions for {symbol}")
            except Exception as e:
                self.logger.error(f"Error closing positions for {symbol}: {str(e)}")
    
    def _generate_post_news_signals(self, event: Dict[str, Any]) -> None:
        """
        Generate trading signals after a news event.
        
        Args:
            event: News event dictionary
        """
        currency = event.get("currency", "")
        event_name = event.get("event", "")
        category = event.get("category", "other")
        
        affected_symbols = self._get_affected_symbols(currency)
        
        if not affected_symbols:
            return
            
        # Wait for the market to react
        time.sleep(self.post_news_reaction * 60)
        
        # Analyze the initial price movement
        for symbol in affected_symbols:
            try:
                if not self.broker:
                    continue
                    
                # Get recent price data
                current_data = self.broker.get_current_price_data(symbol)
                
                if not current_data:
                    continue
                    
                # Determine trade direction based on initial movement
                direction = self._determine_news_direction(symbol, event, current_data)
                
                if direction == 0:
                    continue
                    
                # Calculate position size
                account_info = self.broker.get_account_info()
                position_size = self._calculate_position_size(
                    symbol, 
                    account_info["balance"], 
                    self.risk_per_trade,
                    current_data
                )
                
                # Generate signal
                signal = {
                    "symbol": symbol,
                    "type": "market",
                    "action": "buy" if direction > 0 else "sell",
                    "size": position_size,
                    "reason": f"News reaction: {event_name}",
                    "stop_loss": self._calculate_stop_loss(symbol, direction, current_data),
                    "take_profit": self._calculate_take_profit(symbol, direction, current_data),
                    "entry_time": datetime.now(),
                    "exit_time": datetime.now() + timedelta(minutes=self.position_hold_time)
                }
                
                self.logger.info(f"Generated signal for {symbol}: {signal['action']}, size: {position_size}")
                
                # Add to signals list for execution
                self.event_queue.append({
                    "type": "trade_signal",
                    "timestamp": datetime.now(),
                    "importance": 1.0,  # High importance for trade signals
                    "signal": signal
                })
                
            except Exception as e:
                self.logger.error(f"Error generating signal for {symbol}: {str(e)}")
    
    def _determine_news_direction(self, symbol: str, event: Dict[str, Any], price_data: Dict[str, Any]) -> int:
        """
        Determine the trade direction based on the news and initial price movement.
        
        Args:
            symbol: Trading symbol
            event: News event dictionary
            price_data: Current price data
            
        Returns:
            int: Direction (1 for buy, -1 for sell, 0 for no trade)
        """
        # Simple implementation - use the direction of the first candle after the news
        if "open" in price_data and "close" in price_data:
            if price_data["close"] > price_data["open"]:
                return 1  # Buy
            elif price_data["close"] < price_data["open"]:
                return -1  # Sell
                
        return 0  # No trade
    
    def _calculate_position_size(self, symbol: str, balance: float, risk_percent: float, price_data: Dict[str, Any]) -> float:
        """
        Calculate position size based on account balance and risk percentage.
        
        Args:
            symbol: Trading symbol
            balance: Account balance
            risk_percent: Percentage of balance to risk
            price_data: Current price data
            
        Returns:
            float: Position size
        """
        # Calculate the dollar amount to risk
        risk_amount = balance * (risk_percent / 100)
        
        # Calculate stop loss distance in pips
        stop_loss_pips = self._calculate_stop_loss_pips(symbol, price_data)
        
        # Convert to position size
        if stop_loss_pips > 0 and self.broker:
            # Get symbol information
            symbol_info = self.broker.get_symbol_info(symbol)
            
            if symbol_info:
                # Calculate position size
                pip_value = self.broker.get_pip_value(symbol)
                
                if pip_value > 0:
                    position_size = risk_amount / (stop_loss_pips * pip_value)
                    
                    # Round to standard lot size
                    lot_step = symbol_info.volume_step
                    position_size = round(position_size / lot_step) * lot_step
                    
                    return position_size
        
        # Default to minimum position size
        return 0.01  # Minimum 0.01 lots
    
    def _calculate_stop_loss_pips(self, symbol: str, price_data: Dict[str, Any]) -> float:
        """
        Calculate stop loss distance in pips based on recent volatility.
        
        Args:
            symbol: Trading symbol
            price_data: Current price data
            
        Returns:
            float: Stop loss distance in pips
        """
        # Use average volatility if available, otherwise use a fixed value
        volatility = self.avg_volatility.get(symbol, 0)
        
        if volatility <= 0:
            # Fallback to high-low range from price data
            if "high" in price_data and "low" in price_data:
                volatility = price_data["high"] - price_data["low"]
            else:
                # Default value
                return 20.0  # 20 pips default
        
        # Adjust volatility based on news impact
        adjusted_volatility = volatility * self.news_volatility_factor
        
        # Convert to pips
        if self.broker:
            point = self.broker.point
            if point > 0:
                return adjusted_volatility / point
        
        return adjusted_volatility * 10000  # Assuming 4-digit quotes
    
    def _calculate_stop_loss(self, symbol: str, direction: int, price_data: Dict[str, Any]) -> float:
        """
        Calculate stop loss price.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction (1 for buy, -1 for sell)
            price_data: Current price data
            
        Returns:
            float: Stop loss price
        """
        stop_pips = self._calculate_stop_loss_pips(symbol, price_data)
        
        if direction > 0:  # Buy
            return price_data["close"] - (stop_pips * self.broker.point if self.broker else stop_pips * 0.0001)
        else:  # Sell
            return price_data["close"] + (stop_pips * self.broker.point if self.broker else stop_pips * 0.0001)
    
    def _calculate_take_profit(self, symbol: str, direction: int, price_data: Dict[str, Any]) -> float:
        """
        Calculate take profit price.
        
        Args:
            symbol: Trading symbol
            direction: Trade direction (1 for buy, -1 for sell)
            price_data: Current price data
            
        Returns:
            float: Take profit price
        """
        stop_pips = self._calculate_stop_loss_pips(symbol, price_data)
        take_pips = stop_pips * self.target_profit_ratio
        
        if direction > 0:  # Buy
            return price_data["close"] + (take_pips * self.broker.point if self.broker else take_pips * 0.0001)
        else:  # Sell
            return price_data["close"] - (take_pips * self.broker.point if self.broker else take_pips * 0.0001)
    
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on the strategy logic.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        signals = []
        
        # Process any trade signals in the event queue
        for event in list(self.event_queue):
            if event.get("type") == "trade_signal":
                signal = event.get("signal")
                if signal:
                    signals.append(signal)
                    self.event_queue.remove(event)
        
        return signals
    
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
        Manage existing positions (apply trailing stops, take profits, etc.)
        
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
                
                # Check if the position has been open long enough
                position_age = (datetime.now() - open_time).total_seconds() / 60  # minutes
                
                # If position has been open longer than the hold time, close it
                if position_age >= self.position_hold_time:
                    result = self.broker.close_position(ticket)
                    
                    if result:
                        self.logger.info(f"Closed position {ticket} after {position_age:.1f} minutes")
                        
                        # Add result
                        close_result = {
                            "symbol": symbol,
                            "ticket": ticket,
                            "action": "close",
                            "profit": result.get("profit", 0),
                            "time": datetime.now(),
                            "type": "close_position",
                            "reason": f"Position hold time ({self.position_hold_time} min) elapsed"
                        }
                        
                        results.append(close_result)
                
            except Exception as e:
                self.logger.error(f"Error managing position: {str(e)}")
                
        return results
    
    def manage_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply risk management rules to the signals before execution.
        
        Args:
            signals: List of signals to risk-manage
            
        Returns:
            List[Dict]: Risk-adjusted signals
        """
        # First, check if any high-impact news is imminent
        imminent_news = False
        
        if not self.news_calendar.empty:
            high_impact_soon = self.news_calendar[
                (self.news_calendar["impact_value"] >= self.impact_threshold) & 
                (self.news_calendar["time_until"] <= self.pre_news_buffer) &
                (self.news_calendar["time_until"] > 0)
            ]
            
            imminent_news = not high_impact_soon.empty
        
        # If high-impact news is imminent, don't take new positions
        if imminent_news:
            self.logger.info("High-impact news imminent. Not taking new positions.")
            return []
        
        risk_adjusted_signals = []
        
        for signal in signals:
            symbol = signal.get("symbol", "")
            
            # Skip symbols with excessive spread
            if self.broker:
                current_spread = self.broker.get_current_spread(symbol)
                avg_spread = self.avg_spreads.get(symbol, 0)
                
                if avg_spread > 0 and current_spread > avg_spread * self.max_spread_factor:
                    self.logger.info(f"Skipping {symbol} due to excessive spread: {current_spread} > {avg_spread * self.max_spread_factor}")
                    continue
            
            # Apply position sizing
            # (already done in generate_post_news_signals)
            
            risk_adjusted_signals.append(signal)
        
        return risk_adjusted_signals
    
    def _calculate_event_sentiment(self) -> float:
        """
        Calculate market sentiment based on recent events.
        
        Returns:
            float: Sentiment score (-1.0 to 1.0)
        """
        # Count recent high-impact events
        positive_events = 0
        negative_events = 0
        total_weight = 0
        
        for event in self.event_queue:
            event_type = event.get("type", "")
            importance = event.get("importance", 0)
            
            if event_type == "economic_release" and importance > 0:
                # Get forecast vs previous
                forecast = event.get("forecast", "")
                previous = event.get("previous", "")
                
                # Try to convert to numbers
                try:
                    forecast_val = self._extract_number(forecast)
                    previous_val = self._extract_number(previous)
                    
                    if forecast_val is not None and previous_val is not None:
                        if forecast_val > previous_val:
                            positive_events += importance
                        elif forecast_val < previous_val:
                            negative_events += importance
                        
                        total_weight += importance
                except:
                    pass
        
        # Calculate sentiment score
        if total_weight > 0:
            return (positive_events - negative_events) / total_weight
        
        return 0.0
    
    def _extract_number(self, value_str: str) -> Optional[float]:
        """
        Extract a number from a string, handling percentage values.
        
        Args:
            value_str: String containing a number
            
        Returns:
            Optional[float]: Extracted number, or None if not found
        """
        if not isinstance(value_str, str):
            return None
            
        # Remove non-numeric characters except for decimal point and minus sign
        # But keep the % sign to check if it's a percentage
        cleaned = value_str.replace(',', '')
        
        # Check for percentage
        is_percent = '%' in cleaned
        if is_percent:
            cleaned = cleaned.replace('%', '')
            
        # Find all numbers in the string
        matches = re.findall(r'-?\d+\.?\d*', cleaned)
        
        if matches:
            # Convert to float
            try:
                value = float(matches[0])
                return value
            except:
                return None
                
        return None 