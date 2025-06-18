#!/usr/bin/env python3
"""
Base class for session-based trading strategies.
These strategies focus on trading during specific market sessions (Asian, European, US)
and exploit patterns that emerge during those sessions.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, time, timedelta
import pytz

from src.strategies.base_strategy import BaseStrategy
from src.utils.logger import setup_logger

class SessionStrategyBase(BaseStrategy):
    """Base class for session-based trading strategies."""
    
    # Market session definitions (UTC times)
    SESSIONS = {
        "sydney": {
            "start": time(22, 0),  # 10 PM UTC
            "end": time(7, 0),     # 7 AM UTC
            "timezone": pytz.timezone("Australia/Sydney")
        },
        "tokyo": {
            "start": time(0, 0),   # 12 AM UTC
            "end": time(9, 0),     # 9 AM UTC
            "timezone": pytz.timezone("Asia/Tokyo")
        },
        "london": {
            "start": time(8, 0),   # 8 AM UTC
            "end": time(16, 0),    # 4 PM UTC
            "timezone": pytz.timezone("Europe/London")
        },
        "new_york": {
            "start": time(13, 0),  # 1 PM UTC
            "end": time(22, 0),    # 10 PM UTC
            "timezone": pytz.timezone("America/New_York")
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the session-based strategy.
        
        Args:
            config: Strategy configuration dictionary
        """
        super().__init__(config)
        self.logger = setup_logger(f"{self.__class__.__name__}", f"logs/strategies/{self.__class__.__name__}.log")
        
        # Session-specific configuration
        self.target_sessions = config.get("target_sessions", ["london", "new_york"])
        self.timezone = pytz.timezone(config.get("timezone", "UTC"))
        self.pre_session_prep_time = config.get("pre_session_prep_time", 15)  # minutes
        self.post_session_eval_time = config.get("post_session_eval_time", 15)  # minutes
        
        # Session state
        self.current_session = None
        self.session_start_time = None
        self.session_end_time = None
        self.in_active_session = False
        self.session_stats = {}
        
    def initialize(self) -> bool:
        """
        Initialize the session-based strategy.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing session-based strategy: {self.__class__.__name__}")
        
        # Validate target sessions
        for session in self.target_sessions:
            if session not in self.SESSIONS:
                self.logger.error(f"Invalid session specified: {session}")
                return False
                
        self.logger.info(f"Trading sessions: {', '.join(self.target_sessions)}")
        return True
        
    def is_session_active(self, session_name: str, current_time: Optional[datetime] = None) -> bool:
        """
        Check if a specific market session is currently active.
        
        Args:
            session_name: Name of the session to check
            current_time: Current time (defaults to now)
            
        Returns:
            bool: True if the session is active, False otherwise
        """
        if session_name not in self.SESSIONS:
            return False
            
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
        elif current_time.tzinfo is None:
            current_time = pytz.UTC.localize(current_time)
            
        session = self.SESSIONS[session_name]
        current_utc_time = current_time.astimezone(pytz.UTC).time()
        
        # Handle sessions that cross midnight
        if session["start"] < session["end"]:
            return session["start"] <= current_utc_time < session["end"]
        else:
            return current_utc_time >= session["start"] or current_utc_time < session["end"]
            
    def get_current_session(self, current_time: Optional[datetime] = None) -> Optional[str]:
        """
        Get the name of the currently active trading session.
        
        Args:
            current_time: Current time (defaults to now)
            
        Returns:
            Optional[str]: Name of the active session, or None if no session is active
        """
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
            
        for session_name in self.target_sessions:
            if self.is_session_active(session_name, current_time):
                return session_name
                
        return None
        
    def time_until_session(self, session_name: str, current_time: Optional[datetime] = None) -> Optional[timedelta]:
        """
        Calculate time until the next occurrence of a specific session.
        
        Args:
            session_name: Name of the session
            current_time: Current time (defaults to now)
            
        Returns:
            Optional[timedelta]: Time until the session starts, or None if invalid
        """
        if session_name not in self.SESSIONS:
            return None
            
        if current_time is None:
            current_time = datetime.now(pytz.UTC)
        elif current_time.tzinfo is None:
            current_time = pytz.UTC.localize(current_time)
            
        session = self.SESSIONS[session_name]
        current_date = current_time.date()
        current_utc_time = current_time.astimezone(pytz.UTC).time()
        
        # Create datetime for session start today
        session_start_today = datetime.combine(current_date, session["start"]).replace(tzinfo=pytz.UTC)
        
        # If the session has already started today, calculate for tomorrow
        if current_utc_time >= session["start"]:
            session_start_today += timedelta(days=1)
            
        time_diff = session_start_today - current_time.astimezone(pytz.UTC)
        return time_diff
        
    def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze the market conditions based on the current session.
        
        Returns:
            Dict: Analysis results
        """
        current_time = datetime.now(pytz.UTC)
        current_session = self.get_current_session(current_time)
        
        # Update session state
        if current_session != self.current_session:
            if current_session is not None:
                self.logger.info(f"Entering new session: {current_session}")
                self._on_session_start(current_session)
            elif self.current_session is not None:
                self.logger.info(f"Exiting session: {self.current_session}")
                self._on_session_end(self.current_session)
                
            self.current_session = current_session
            
        # Calculate next session if not in a session
        next_session_info = None
        if current_session is None:
            next_session = None
            min_time_delta = timedelta(days=1)
            
            for session_name in self.target_sessions:
                time_delta = self.time_until_session(session_name, current_time)
                if time_delta and time_delta < min_time_delta:
                    min_time_delta = time_delta
                    next_session = session_name
                    
            if next_session:
                next_session_info = {
                    "name": next_session,
                    "time_until": min_time_delta.total_seconds() / 60  # minutes
                }
            
        # Return analysis results
        return {
            "current_session": current_session,
            "next_session": next_session_info,
            "in_active_session": current_session is not None,
            "current_time_utc": current_time,
            "session_stats": self.session_stats.get(current_session, {})
        }
        
    def _on_session_start(self, session_name: str) -> None:
        """
        Handle session start event.
        
        Args:
            session_name: Name of the session that is starting
        """
        self.logger.info(f"Session {session_name} started")
        self.session_start_time = datetime.now(pytz.UTC)
        self.in_active_session = True
        
        # Initialize session statistics
        self.session_stats[session_name] = {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "profit": 0.0,
            "start_time": self.session_start_time
        }
        
        # Perform session-specific initialization
        # This should be implemented by subclasses
        pass
        
    def _on_session_end(self, session_name: str) -> None:
        """
        Handle session end event.
        
        Args:
            session_name: Name of the session that is ending
        """
        self.logger.info(f"Session {session_name} ended")
        self.session_end_time = datetime.now(pytz.UTC)
        self.in_active_session = False
        
        # Update session statistics
        if session_name in self.session_stats:
            self.session_stats[session_name]["end_time"] = self.session_end_time
            self.session_stats[session_name]["duration"] = (
                self.session_end_time - self.session_stats[session_name]["start_time"]
            ).total_seconds() / 3600  # hours
            
        # Perform session-specific cleanup
        # This should be implemented by subclasses
        pass
        
    def generate_signals(self) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on the current session and market conditions.
        
        Returns:
            List[Dict]: List of signal dictionaries
        """
        # Only generate signals during active sessions
        if not self.in_active_session:
            return []
            
        # This should be implemented by subclasses
        return [] 