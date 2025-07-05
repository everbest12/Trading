#!/usr/bin/env python3
"""
Base class for event-driven trading strategies.
These strategies react to market news, economic events, and other external triggers.
"""

import threading
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime, timedelta

from src.strategies.base_strategy import BaseStrategy
from src.utils.logger import setup_logger

class EventStrategyBase(BaseStrategy):
    """Base class for event-driven trading strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the event-driven strategy base.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__(config)
        self.logger = setup_logger(f"{self.__class__.__name__}", f"logs/strategies/{self.__class__.__name__}.log")
        
        # Event-specific configuration
        self.event_sources = config.get("event_sources", [])
        self.event_types = config.get("event_types", [])
        self.event_threshold = config.get("event_threshold", 0.5)
        self.reaction_delay = config.get("reaction_delay", 0.0)  # Delay in seconds
        
        # Event monitoring
        self.event_listeners = []
        self.event_queue = []
        self.event_thread = None
        self.event_thread_running = False
        
    def initialize(self) -> bool:
        """
        Initialize the event-driven strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing event-driven strategy: {self.__class__.__name__}")
        
        # Start event monitoring thread
        self.event_thread_running = True
        self.event_thread = threading.Thread(target=self._event_monitoring_loop)
        self.event_thread.daemon = True
        self.event_thread.start()
        
        self.logger.info("Event monitoring thread started")
        return True
        
    def _event_monitoring_loop(self) -> None:
        """Background thread for monitoring events from various sources."""
        self.logger.info("Event monitoring loop started")
        
        while self.event_thread_running:
            try:
                # Check for new events from all sources
                for source in self.event_sources:
                    new_events = self._poll_event_source(source)
                    if new_events:
                        self.event_queue.extend(new_events)
                        self.logger.info(f"Received {len(new_events)} new events from {source}")
                
                # Process any events in the queue
                if self.event_queue:
                    self._process_event_queue()
                    
                # Sleep to avoid excessive CPU usage
                threading.Event().wait(1.0)  # 1-second polling interval
                
            except Exception as e:
                self.logger.error(f"Error in event monitoring loop: {str(e)}")
    
    def _poll_event_source(self, source: str) -> List[Dict[str, Any]]:
        """
        Poll an event source for new events.
        
        Args:
            source: Name of the event source
            
        Returns:
            List[Dict]: List of event dictionaries
        """
        # Implement specific polling logic for different event sources
        return []
    
    def _process_event_queue(self) -> None:
        """Process events in the event queue."""
        current_time = datetime.now()
        processed_events = []
        
        for event in self.event_queue:
            # Check if the event is ready to be processed (accounting for reaction delay)
            event_time = event.get("timestamp", current_time)
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time)
                
            if current_time >= event_time + timedelta(seconds=self.reaction_delay):
                # Process the event
                self._process_event(event)
                processed_events.append(event)
        
        # Remove processed events from the queue
        for event in processed_events:
            self.event_queue.remove(event)
    
    def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event.
        
        Args:
            event: Event dictionary
        """
        event_type = event.get("type", "unknown")
        event_importance = event.get("importance", 0.0)
        
        self.logger.info(f"Processing event: {event_type} (importance: {event_importance})")
        
        # Only react to events that meet the threshold
        if event_importance >= self.event_threshold and event_type in self.event_types:
            self.logger.info(f"Event meets threshold, triggering reaction")
            self._react_to_event(event)
    
    def _react_to_event(self, event: Dict[str, Any]) -> None:
        """
        React to an event by generating signals.
        
        Args:
            event: Event dictionary
        """
        # This should be implemented by subclasses
        pass
    
    def register_event_listener(self, event_type: str, callback: Callable) -> None:
        """
        Register a callback function for a specific event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Callback function to invoke when event occurs
        """
        self.event_listeners.append({
            "event_type": event_type,
            "callback": callback
        })
        
    def stop(self) -> None:
        """Stop the strategy execution."""
        self.logger.info("Stopping event-driven strategy")
        self.event_thread_running = False
        if self.event_thread and self.event_thread.is_alive():
            self.event_thread.join(timeout=5.0)
        super().stop()
        
    def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze the market conditions based on recent events.
        
        Returns:
            Dict: Analysis results
        """
        # Basic implementation - should be enhanced in subclasses
        return {
            "event_count": len(self.event_queue),
            "last_processed_time": datetime.now(),
            "market_sentiment": self._calculate_event_sentiment()
        }
    
    def _calculate_event_sentiment(self) -> float:
        """
        Calculate market sentiment based on recent events.
        
        Returns:
            float: Sentiment score (-1.0 to 1.0)
        """
        # This should be implemented by subclasses
        return 0.0 