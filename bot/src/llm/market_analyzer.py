import os
import json
from typing import Dict, Any, List, Optional
import openai
import pandas as pd
from datetime import datetime, timedelta

class MarketAnalyzer:
    """
    Uses LLM to analyze market conditions and provide insights.
    """
    
    def __init__(self, config_path: str):
        """Initialize the market analyzer with configuration."""
        self.config = self._load_config(config_path)
        self._setup_api()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        with open(config_path, 'r') as file:
            return json.load(file)
    
    def _setup_api(self) -> None:
        """Set up the OpenAI API client."""
        openai.api_key = self.config.get('openai', {}).get('api_key', os.getenv('OPENAI_API_KEY'))
        if not openai.api_key:
            raise ValueError("OpenAI API key not found in config or environment variables")
    
    def analyze_market_data(
        self, 
        symbol: str, 
        market_data: pd.DataFrame, 
        technical_indicators: Dict[str, pd.Series],
        news_items: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze market data using LLM and generate insights.
        
        Args:
            symbol: The market symbol (e.g., "EURUSD")
            market_data: DataFrame with OHLCV data
            technical_indicators: Dictionary of technical indicators
            news_items: List of relevant news items (optional)
            
        Returns:
            Dictionary with market analysis and insights
        """
        # Prepare market data summary
        market_summary = self._prepare_market_summary(symbol, market_data, technical_indicators)
        
        # Prepare news summary if available
        news_summary = self._prepare_news_summary(news_items) if news_items else ""
        
        # Create prompt for the LLM
        prompt = f"""
        Please analyze the following market data for {symbol}:
        
        {market_summary}
        
        {news_summary}
        
        Provide a comprehensive analysis including:
        1. Current market trend and key levels
        2. Technical indicator signals and what they suggest
        3. Key support and resistance levels
        4. Potential trading opportunities with entry, stop loss, and take profit levels
        5. Overall market sentiment and forecast
        
        Format your response in a structured way with clear sections and actionable insights.
        """
        
        # Call the OpenAI API
        response = openai.ChatCompletion.create(
            model=self.config.get('openai', {}).get('model', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are an expert forex market analyst with deep knowledge of technical analysis, market patterns, and trading strategies."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.get('openai', {}).get('temperature', 0.3),
            max_tokens=self.config.get('openai', {}).get('max_tokens', 1500)
        )
        
        # Extract and parse the response
        analysis_text = response.choices[0].message.content
        
        # Save the analysis
        analysis_file = self._save_analysis(symbol, analysis_text)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis_text,
            "data_summary": market_summary,
            "news_summary": news_summary,
            "analysis_file": analysis_file
        }
    
    def _prepare_market_summary(
        self, 
        symbol: str, 
        market_data: pd.DataFrame, 
        technical_indicators: Dict[str, pd.Series]
    ) -> str:
        """Prepare a summary of market data for the LLM."""
        # Extract recent candles
        recent_candles = market_data.tail(10).copy()
        
        # Format candle data
        candle_summary = "Recent price action:\n"
        for idx, row in recent_candles.iterrows():
            candle_summary += f"{idx.strftime('%Y-%m-%d %H:%M')}: O={row['open']:.5f}, H={row['high']:.5f}, L={row['low']:.5f}, C={row['close']:.5f}, V={row['volume']}\n"
        
        # Format technical indicators
        indicator_summary = "Technical indicators:\n"
        for indicator_name, indicator_values in technical_indicators.items():
            recent_values = indicator_values.tail(3)
            indicator_summary += f"{indicator_name}: {', '.join([f'{val:.5f}' for val in recent_values])}\n"
        
        # Add current price and daily change
        if not recent_candles.empty:
            current_price = recent_candles.iloc[-1]['close']
            prev_day = recent_candles.iloc[0]['close']
            daily_change = ((current_price - prev_day) / prev_day) * 100
            
            price_summary = f"""
            Current price: {current_price:.5f}
            Daily change: {daily_change:.2f}%
            """
        else:
            price_summary = "No price data available"
        
        return f"{price_summary}\n\n{candle_summary}\n\n{indicator_summary}"
    
    def _prepare_news_summary(self, news_items: List[Dict[str, Any]]) -> str:
        """Prepare a summary of news items for the LLM."""
        if not news_items:
            return "No recent news available."
        
        news_summary = "Recent market news:\n"
        for item in news_items[:5]:  # Limit to most recent 5 items
            news_summary += f"- {item.get('date', 'N/A')} - {item.get('title', 'N/A')}: {item.get('summary', 'N/A')}\n"
        
        return news_summary
    
    def _save_analysis(self, symbol: str, analysis: str) -> str:
        """Save the market analysis to a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_path = f"data/market_analysis/{symbol}"
        filename = f"{dir_path}/{timestamp}_analysis.txt"
        
        # Ensure directory exists
        os.makedirs(dir_path, exist_ok=True)
        
        # Save the analysis
        with open(filename, 'w') as file:
            file.write(analysis)
            
        return filename
    
    def analyze_economic_news(self, news_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an economic news item and determine its potential market impact.
        
        Args:
            news_item: Dictionary containing news details (title, content, date, etc.)
            
        Returns:
            Dictionary with analysis of market impact
        """
        # Create prompt for the LLM
        prompt = f"""
        Please analyze the following economic news and determine its potential market impact:
        
        Title: {news_item.get('title', 'N/A')}
        Date: {news_item.get('date', 'N/A')}
        Content: {news_item.get('content', 'N/A')}
        
        Provide:
        1. A summary of the news
        2. The potential market impact (bullish, bearish, or neutral)
        3. Which currency pairs or markets are most likely to be affected
        4. Potential trading opportunities based on this news
        5. Risk assessment for trading based on this news
        
        Format your response in a structured way with clear sections.
        """
        
        # Call the OpenAI API
        response = openai.ChatCompletion.create(
            model=self.config.get('openai', {}).get('model', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are an expert in economic news analysis and forex market impact. Your task is to analyze economic news and determine its potential impact on currency markets."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.get('openai', {}).get('temperature', 0.3),
            max_tokens=self.config.get('openai', {}).get('max_tokens', 1000)
        )
        
        # Extract and parse the response
        analysis_text = response.choices[0].message.content
        
        return {
            "news_item": news_item,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis_text
        }
    
    def generate_daily_outlook(
        self, 
        symbols: List[str],
        market_data: Dict[str, pd.DataFrame],
        economic_calendar: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a daily market outlook for multiple symbols.
        
        Args:
            symbols: List of market symbols to analyze
            market_data: Dictionary mapping symbols to their respective DataFrame with OHLCV data
            economic_calendar: List of economic events scheduled for the day
            
        Returns:
            Dictionary with daily market outlook
        """
        # Prepare market summaries
        market_summaries = []
        for symbol in symbols:
            if symbol in market_data:
                # Get just the recent price and daily change
                df = market_data[symbol].tail(1)
                if not df.empty:
                    current_price = df.iloc[0]['close']
                    prev_day_price = market_data[symbol].iloc[-2]['close'] if len(market_data[symbol]) > 1 else current_price
                    daily_change = ((current_price - prev_day_price) / prev_day_price) * 100
                    market_summaries.append(f"{symbol}: {current_price:.5f} ({daily_change:+.2f}%)")
        
        # Prepare economic calendar summary
        calendar_summary = "Today's economic events:\n"
        if economic_calendar:
            for event in economic_calendar:
                calendar_summary += f"- {event.get('time', 'N/A')} - {event.get('country', 'N/A')} - {event.get('event', 'N/A')} (Impact: {event.get('impact', 'N/A')})\n"
        else:
            calendar_summary = "No major economic events scheduled for today."
        
        # Create prompt for the LLM
        prompt = f"""
        Please generate a daily market outlook for {', '.join(symbols)} based on the following information:
        
        Current market prices:
        {chr(10).join(market_summaries)}
        
        {calendar_summary}
        
        Provide:
        1. Overall market sentiment for the day
        2. Key levels to watch for each symbol
        3. Potential trading opportunities
        4. Risk events to be aware of
        5. Trading strategy recommendations for the day
        
        Format your response in a structured way with clear sections for each symbol.
        """
        
        # Call the OpenAI API
        response = openai.ChatCompletion.create(
            model=self.config.get('openai', {}).get('model', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are an expert forex market analyst providing daily market outlooks and trading recommendations."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.get('openai', {}).get('temperature', 0.3),
            max_tokens=self.config.get('openai', {}).get('max_tokens', 2000)
        )
        
        # Extract and parse the response
        outlook_text = response.choices[0].message.content
        
        # Save the outlook
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"data/market_analysis/daily_outlook_{timestamp}.txt"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Save the outlook
        with open(filename, 'w') as file:
            file.write(outlook_text)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "symbols": symbols,
            "outlook": outlook_text,
            "outlook_file": filename
        }