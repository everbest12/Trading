import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import pytz
from typing import Dict, Any, Optional, List, Tuple

class MT5Connector:
    """Connector for MetaTrader 5 platform."""
    
    def __init__(self, config_path: str):
        """Initialize MT5 connector with configuration."""
        self.config = self._load_config(config_path)
        self.connected = False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        import json
        with open(config_path, 'r') as file:
            return json.load(file)
    
    def connect(self) -> bool:
        """Establish connection to MT5 terminal."""
        if not mt5.initialize(
            login=self.config.get('login'),
            password=self.config.get('password'),
            server=self.config.get('server'),
            path=self.config.get('terminal_path')
        ):
            print(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        self.connected = True
        print(f"Connected to MT5: {mt5.terminal_info()}")
        print(f"Account info: {mt5.account_info()}")
        return True
    
    def disconnect(self) -> None:
        """Disconnect from MT5 terminal."""
        mt5.shutdown()
        self.connected = False
        print("Disconnected from MT5")
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        account_info = mt5.account_info()
        if account_info is None:
            raise RuntimeError(f"Failed to get account info: {mt5.last_error()}")
        
        return {
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'free_margin': account_info.margin_free,
            'leverage': account_info.leverage,
            'currency': account_info.currency
        }
    
    def place_market_order(
        self, 
        symbol: str, 
        order_type: str, 
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "MT5 Market Order"
    ) -> int:
        """Place a market order."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        # Map order type string to MT5 constants
        order_type_map = {
            "BUY": mt5.ORDER_TYPE_BUY,
            "SELL": mt5.ORDER_TYPE_SELL
        }
        
        if order_type not in order_type_map:
            raise ValueError(f"Invalid order type: {order_type}. Must be one of {list(order_type_map.keys())}")
        
        # Prepare order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type_map[order_type],
            "price": mt5.symbol_info_tick(symbol).ask if order_type == "BUY" else mt5.symbol_info_tick(symbol).bid,
            "deviation": 10,  # Maximum price deviation in points
            "magic": 12345,   # Magic number for order identification
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        # Add stop loss and take profit if provided
        if stop_loss is not None:
            request["sl"] = stop_loss
        if take_profit is not None:
            request["tp"] = take_profit
        
        # Send order
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order failed: {result.retcode}. Comment: {result.comment}")
        
        print(f"Order placed successfully. Order ID: {result.order}")
        return result.order
    
    def get_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        from_date: datetime, 
        to_date: datetime = None
    ) -> pd.DataFrame:
        """Get historical price data."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        # Map timeframe string to MT5 constants
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }
        
        if timeframe not in timeframe_map:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {list(timeframe_map.keys())}")
        
        # Set timezone to UTC
        timezone = pytz.timezone("Etc/UTC")
        from_date = timezone.localize(from_date)
        if to_date is None:
            to_date = datetime.now(timezone)
        else:
            to_date = timezone.localize(to_date)
        
        # Get historical data
        rates = mt5.copy_rates_range(symbol, timeframe_map[timeframe], from_date, to_date)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Failed to get historical data: {mt5.last_error()}")
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def get_open_positions(self) -> pd.DataFrame:
        """Get currently open positions."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['time_update'] = pd.to_datetime(df['time_update'], unit='s')
        
        return df
    
    def close_position(self, position_id: int) -> bool:
        """Close a specific position by its ID."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        # Get position details
        position = mt5.positions_get(ticket=position_id)
        if position is None or len(position) == 0:
            raise ValueError(f"Position with ID {position_id} not found")
        
        position = position[0]
        
        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position_id,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": 10,
            "magic": 12345,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        # Send close request
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Close position failed: {result.retcode}. Comment: {result.comment}")
        
        print(f"Position {position_id} closed successfully")
        return True
    
    def get_symbols(self) -> List[str]:
        """Get list of available symbols."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        symbols = mt5.symbols_get()
        return [symbol.name for symbol in symbols]
    
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get detailed information about a symbol."""
        if not self.connected:
            raise ConnectionError("Not connected to MT5")
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"Symbol {symbol} not found")
        
        return symbol_info._asdict()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect() 