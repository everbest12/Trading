from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.brokers.mt5_connector import MT5Connector
from src.indicators.momentum.rsi import calculate_rsi, get_rsi_signal
from src.utils.logger import setup_logger

class RSIStrategy:
    """
    RSI-based trading strategy that buys when RSI is oversold and sells when RSI is overbought.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize RSI strategy with configuration."""
        self.config = config
        self.symbol = config['symbol']
        self.timeframe = config['timeframe']
        self.rsi_period = config.get('rsi_period', 14)
        self.overbought = config.get('overbought', 70)
        self.oversold = config.get('oversold', 30)
        self.risk_percent = config.get('risk_percent', 1.0)
        
        # Initialize connector
        self.connector = MT5Connector(config['mt5_config_path'])
        
        # Setup logger
        self.logger = setup_logger(f"rsi_strategy_{self.symbol}_{self.timeframe}", "logs/trades/rsi_strategy.log")
        
        # Strategy state
        self.position = None
        self.last_signal = None
    
    def start(self) -> bool:
        """Start the strategy."""
        try:
            self.logger.info(f"Starting RSI strategy for {self.symbol} on {self.timeframe}")
            return self.connector.connect()
        except Exception as e:
            self.logger.error(f"Failed to start strategy: {str(e)}")
            return False
    
    def stop(self) -> None:
        """Stop the strategy."""
        try:
            self.logger.info("Stopping RSI strategy")
            self.connector.disconnect()
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {str(e)}")
    
    def get_market_data(self) -> pd.DataFrame:
        """Get recent market data for analysis."""
        try:
            # Get data for period calculation plus some buffer
            from_date = datetime.now() - timedelta(days=10)  # Adjust based on timeframe
            data = self.connector.get_historical_data(
                self.symbol, 
                self.timeframe, 
                from_date
            )
            return data
        except Exception as e:
            self.logger.error(f"Error getting market data: {str(e)}")
            return pd.DataFrame()
    
    def analyze_market(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market data and generate signals."""
        if data.empty:
            return {'signal': None, 'rsi': None}
        
        # Calculate RSI
        rsi_values = calculate_rsi(data['close'].values, self.rsi_period)
        current_rsi = rsi_values[-1]
        
        # Generate signal
        signal = get_rsi_signal(current_rsi, self.overbought, self.oversold)
        
        return {
            'signal': signal,
            'rsi': current_rsi
        }
    
    def calculate_position_size(self, account_balance: float, stop_loss_pips: int, current_price: float) -> float:
        """
        Calculate position size based on risk percentage.
        
        Args:
            account_balance: Account balance
            stop_loss_pips: Stop loss in pips
            current_price: Current market price
            
        Returns:
            Position size in lots
        """
        # Risk amount in account currency
        risk_amount = account_balance * (self.risk_percent / 100.0)
        
        # Convert pips to price
        pip_value = 0.0001 if 'JPY' not in self.symbol else 0.01
        stop_loss_amount = stop_loss_pips * pip_value
        
        # Calculate position size (standard lots)
        position_size = risk_amount / (stop_loss_amount * 100000)
        
        # Round to 2 decimal places (minimum step for MT5 is 0.01 lots)
        position_size = round(position_size, 2)
        
        # Ensure minimum position size
        min_lot = 0.01
        if position_size < min_lot:
            position_size = min_lot
            
        return position_size
    
    def execute_signal(self, analysis: Dict[str, Any]) -> Optional[int]:
        """Execute trading signal."""
        signal = analysis.get('signal')
        if signal is None or signal == self.last_signal:
            return None
        
        try:
            # Get account info for position sizing
            account_info = self.connector.get_account_info()
            
            # Calculate position size based on risk percentage
            price = self.get_market_data()['close'].iloc[-1]
            stop_pips = 50  # Example stop loss in pips
            position_size = self.calculate_position_size(
                account_balance=account_info['balance'],
                stop_loss_pips=stop_pips,
                current_price=price
            )
            
            # Calculate stop loss and take profit levels
            pip_value = 0.0001 if 'JPY' not in self.symbol else 0.01
            stop_loss = price - (stop_pips * pip_value) if signal == "BUY" else price + (stop_pips * pip_value)
            take_profit = price + (stop_pips * pip_value * 2) if signal == "BUY" else price - (stop_pips * pip_value * 2)
            
            # Place order
            order_id = self.connector.place_market_order(
                symbol=self.symbol,
                order_type=signal,
                volume=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                comment=f"RSI Strategy: {analysis['rsi']}"
            )
            
            self.last_signal = signal
            self.logger.info(f"Executed {signal} order for {self.symbol}. RSI: {analysis['rsi']}, Size: {position_size}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {str(e)}")
            return None
    
    def run_iteration(self) -> None:
        """Run a single iteration of the strategy."""
        try:
            # Get market data
            data = self.get_market_data()
            if data.empty:
                self.logger.warning("No market data available")
                return
            
            # Analyze market
            analysis = self.analyze_market(data)
            self.logger.info(f"Market analysis: Symbol={self.symbol}, RSI={analysis['rsi']}, Signal={analysis['signal']}")
            
            # Execute signal if available
            if analysis['signal']:
                order_id = self.execute_signal(analysis)
                if order_id:
                    self.logger.info(f"Order executed with ID: {order_id}")
            
        except Exception as e:
            self.logger.error(f"Error in strategy iteration: {str(e)}")
    
    def run(self, iterations: Optional[int] = None) -> None:
        """
        Run the strategy for a specified number of iterations or indefinitely.
        
        Args:
            iterations: Number of iterations to run (None for indefinite)
        """
        try:
            # Start the strategy
            if not self.start():
                self.logger.error("Failed to start strategy")
                return
            
            # Run for specified iterations or indefinitely
            count = 0
            running = True
            
            while running:
                self.run_iteration()
                
                count += 1
                if iterations is not None and count >= iterations:
                    running = False
                
                # Sleep between iterations (adjust as needed)
                import time
                time.sleep(60)  # 1 minute between checks
                
        except KeyboardInterrupt:
            self.logger.info("Strategy stopped by user")
        except Exception as e:
            self.logger.error(f"Strategy error: {str(e)}")
        finally:
            self.stop() 