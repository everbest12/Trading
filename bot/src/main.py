#!/usr/bin/env python3
"""
Main entry point for the algorithmic trading platform.
This script allows running various trading strategies across different asset classes.
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import strategies
from src.strategies.technical.rsi_strategy import RSIStrategy
from src.strategies.event_driven.news_impact_strategy import NewsImpactStrategy
from src.strategies.session_based.london_breakout_strategy import LondonBreakoutStrategy
from src.strategies.day_trading.vwap_reversion_strategy import VWAPReversionStrategy

from src.utils.logger import setup_logger

def load_config(config_path):
    """Load configuration from file."""
    with open(config_path, 'r') as file:
        return json.load(file)

def run_strategy(strategy_class, args):
    """Run a trading strategy."""
    logger = setup_logger("main", "logs/main.log")
    logger.info(f"Starting {strategy_class.__name__} runner")
    
    # Load broker config
    broker_config_path = args.broker_config or f"config/brokers/{args.broker}_config.json"
    if not os.path.exists(broker_config_path):
        logger.error(f"Broker config file not found: {broker_config_path}")
        return
    
    # Load trading parameters
    trading_params_path = args.trading_params or "config/trading_params.json"
    if not os.path.exists(trading_params_path):
        logger.error(f"Trading parameters file not found: {trading_params_path}")
        return
    
    # Load specific strategy config if provided
    strategy_config_path = args.strategy_config or f"config/strategies/{strategy_class.__name__}_config.json"
    strategy_config = {}
    
    if os.path.exists(strategy_config_path):
        strategy_config = load_config(strategy_config_path)
        logger.info(f"Loaded strategy config from {strategy_config_path}")
    else:
        logger.warning(f"Strategy config file not found: {strategy_config_path}. Using default parameters.")
    
    # Add command line arguments to strategy config
    for key, value in vars(args).items():
        if value is not None and key not in ['command', 'strategy', 'broker', 'broker_config', 
                                           'trading_params', 'strategy_config', 'test_mode', 'iterations']:
            strategy_config[key] = value
    
    # Add broker config path
    if args.broker == "mt5":
        strategy_config["mt5_config_path"] = broker_config_path
    else:
        strategy_config[f"{args.broker}_config_path"] = broker_config_path
    
    logger.info(f"Strategy configuration: {strategy_config}")
    
    try:
        # Initialize and run the strategy
        strategy = strategy_class(strategy_config)
        
        if args.test_mode:
            logger.info(f"Running in test mode for {args.iterations} iterations")
            strategy.run(iterations=args.iterations)
        else:
            logger.info("Running in live mode indefinitely")
            strategy.run()
            
    except KeyboardInterrupt:
        logger.info("Strategy stopped by user")
    except Exception as e:
        logger.error(f"Error running strategy: {str(e)}", exc_info=True)
    finally:
        logger.info("Strategy runner completed")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Algorithmic Trading Platform")
    
    # Strategy subcommand
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Common arguments for all strategies
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--broker", type=str, default="mt5", choices=["mt5", "binance", "ib"], 
                               help="Broker to use")
    common_parser.add_argument("--broker-config", type=str, help="Path to broker configuration file")
    common_parser.add_argument("--trading-params", type=str, help="Path to trading parameters file")
    common_parser.add_argument("--strategy-config", type=str, help="Path to strategy configuration file")
    common_parser.add_argument("--test-mode", action="store_true", help="Run in test mode")
    common_parser.add_argument("--iterations", type=int, default=5, help="Number of iterations in test mode")
    common_parser.add_argument("--symbol", type=str, help="Trading symbol")
    common_parser.add_argument("--timeframe", type=str, help="Trading timeframe")
    common_parser.add_argument("--risk-percent", type=float, help="Risk percentage per trade")
    
    # RSI strategy parser
    rsi_parser = subparsers.add_parser("rsi", parents=[common_parser], help="Run RSI strategy")
    rsi_parser.add_argument("--rsi-period", type=int, default=14, help="RSI period")
    rsi_parser.add_argument("--overbought", type=float, default=70.0, help="Overbought threshold")
    rsi_parser.add_argument("--oversold", type=float, default=30.0, help="Oversold threshold")
    
    # News Impact strategy parser
    news_parser = subparsers.add_parser("news", parents=[common_parser], help="Run News Impact strategy")
    news_parser.add_argument("--impact-threshold", type=float, default=0.7, help="Minimum news impact threshold")
    news_parser.add_argument("--pre-news-buffer", type=int, default=5, help="Minutes before news to avoid trading")
    news_parser.add_argument("--post-news-reaction", type=int, default=1, help="Minutes after news before trading")
    news_parser.add_argument("--position-hold-time", type=int, default=15, help="Minutes to hold position")
    
    # London Breakout strategy parser
    london_parser = subparsers.add_parser("london", parents=[common_parser], help="Run London Breakout strategy")
    london_parser.add_argument("--range-hours", type=int, default=3, help="Hours before London open to calculate range")
    london_parser.add_argument("--breakout-trigger", type=float, default=0.5, help="Percentage of range to trigger entry")
    london_parser.add_argument("--stop-loss-factor", type=float, default=1.0, help="Multiple of range for stop loss")
    london_parser.add_argument("--take-profit-factor", type=float, default=2.0, help="Multiple of range for take profit")
    
    # VWAP Reversion strategy parser
    vwap_parser = subparsers.add_parser("vwap", parents=[common_parser], help="Run VWAP Reversion strategy")
    vwap_parser.add_argument("--vwap-deviation", type=float, default=1.5, help="Standard deviations from VWAP to trigger entry")
    vwap_parser.add_argument("--profit-target", type=float, default=0.5, help="Target profit as percentage of VWAP deviation")
    vwap_parser.add_argument("--stop-loss", type=float, default=1.0, help="Stop loss as percentage of VWAP deviation")
    vwap_parser.add_argument("--max-position-size", type=int, default=100, help="Maximum position size in shares")
    
    args = parser.parse_args()
    
    # Map command to strategy class
    strategy_map = {
        "rsi": RSIStrategy,
        "news": NewsImpactStrategy,
        "london": LondonBreakoutStrategy,
        "vwap": VWAPReversionStrategy
    }
    
    if args.command in strategy_map:
        run_strategy(strategy_map[args.command], args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 