import MetaTrader5 as mt5
import pandas as pd
import time
import datetime
import pytz
from datetime import UTC
import logging
from typing import Dict, List, Tuple
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('market_sessions.log')
    ]
)

# Define sessions with trading pairs and their directions (UTC time)
sessions = {
    "Tokyo & Sydney": {  # UTC+9/UTC+10
        "start": datetime.time(22, 0),  # 22:00 UTC (07:00 Tokyo next day)
        "end": datetime.time(7, 0),    # 07:00 UTC (16:00 Tokyo)
        "buy_pairs": [
            "USDJPY",  # Strong during Asian session
            "AUDJPY",  # Influenced by Asian markets
            "EURJPY"   # Good liquidity during Asian session
        ],
        "sell_pairs": [
            "GBPJPY",  # Often reverses during Asian session
            "CADJPY",  # Typically ranges during Asian session
            "CHFJPY"   # Good for counter-trend during Asian session
        ]
    },
    "London": {  # UTC+0/+1
        "start": datetime.time(7, 0),   # 07:00 UTC (08:00 London) 9 Italian time
        "end": datetime.time(16, 0),    # 16:00 UTC (17:00 London)
        "buy_pairs": [
            "EURUSD",  # Highest liquidity during London
            "CHFJPY",
            "EURCHF",
            "EURGBP",
            "EURJPY",
            "GBPJPY",
            # "GBPUSD",  # Major GBP pair with high London liquidity //// stay away from trading the pairs today 17/06/2025 because oof no clear direction

            # "GBPCHF",
            # "USDCHF",
        ],
        "sell_pairs": [
            "GBPCHF",  #Good for range trading in London
            # "GBPUSD",  # Major GBP pair with high London liquidity
            # "EURUSD",  # Highest liquidity during London
            # "EURGBP",
            # "CHFJPY",
            # "EURCHF",  # Sensitive to European news
            # "EURJPY",
            # "GBPJPY",
            # "USDCHF",  #Often moves counter to EURUSD
        ]
    },
    "New York": {  # UTC-4
        "start": datetime.time(13, 0),  # 13:00 UTC (09:00 NY)
        "end": datetime.time(22, 0),    # 22:00 UTC (18:00 NY)
        "buy_pairs": [
            "EURUSD",  # Highest global liquidity
            "USDCAD",  # North American pair
            "XAUUSD",  # Active during NY hours
            "EURCAD",  # Good correlation with USDCAD
            "USDCHF",  # Major USD pair
            "EURJPY",  # High liquidity during NY overlap
            "GBPUSD",  # Active during NY session
            "CADJPY",  # Good for range trading
            "XAUJPY"   # Gold/JPY correlation
        ],
        "sell_pairs": [
            "USDJPY",  # Often reverses during NY close
            "AUDUSD",  # Sensitive to US market moves
            "NZDUSD",  # Good for counter-trend during NY
            "USDSGD",  # Asian currency pair
            "EURGBP",  # European cross
            "GBPJPY",  # High volatility during NY
            "AUDJPY",  # Risk sentiment indicator
            "NZDJPY",  # Good for range trading
            "XAUCHF"   # Gold/CHF correlation
        ]
    }
}

class MarketSessionTrader:
    def __init__(self):
        self.max_positions = 3  # Maximum positions per pair per side
        self.volume = 0.1      # Standard lot size
        self.scalp_multiplier = 0.5  # Multiplier for scalping distances
        self.base_entry_pips = 1  # Base entry distance for scalping
        self.min_spread_multiplier = 1.0  # Minimum distance as multiple of spread
        self.order_expiry_minutes = 30  # Orders expire after 30 minutes
        self.initialized = False
        
    def initialize_mt5(self):
        """Initialize MT5 connection"""
        try:
            if not mt5.initialize():
                raise RuntimeError(f"Initialize() failed: {mt5.last_error()}")
            
            # Verify connection
            if not mt5.terminal_info():
                raise RuntimeError("Terminal info not available")
                
            account_info = mt5.account_info()
            if not account_info:
                raise RuntimeError("Failed to get account info")
                
            logging.info(f"Connected to: {account_info.server}")
            logging.info(f"Account: {account_info.login}")
            logging.info(f"Balance: {account_info.balance}")
            
            self.initialized = True
            logging.info("MT5 initialized successfully")
            
        except Exception as e:
            logging.error(f"MT5 initialization failed: {str(e)}")
            self.initialized = False
            raise

    def verify_symbol(self, symbol: str) -> bool:
        """Verify if symbol is available and enabled for trading"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logging.error(f"Symbol {symbol} not found")
                return False
                
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logging.error(f"Symbol {symbol} selection failed")
                    return False
                    
            if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
                logging.error(f"Symbol {symbol} not available for full trading")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Error verifying symbol {symbol}: {str(e)}")
            return False

    def get_symbol_info(self, symbol: str) -> Dict:
        """Get symbol information including spread"""
        try:
            if not self.verify_symbol(symbol):
                return None
                
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
                
            return {
                "spread": info.spread * info.point,
                "point": info.point,
                "digits": info.digits,
                "trade_mode": info.trade_mode
            }
        except Exception as e:
            logging.error(f"Error getting symbol info for {symbol}: {str(e)}")
            return None

    def send_order(self, order_request: Dict) -> bool:
        """Send order with proper error handling"""
        try:
            if not self.initialized:
                logging.error("MT5 not initialized")
                return False
                
            result = mt5.order_send(order_request)
            if result is None:
                error = mt5.last_error()
                logging.error(f"Order send failed: {error}")
                return False
                
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logging.error(f"Order failed: {result.retcode}, {result.comment}")
                return False
                
            logging.info(f"Order placed successfully: {result.order}")
            return True
            
        except Exception as e:
            logging.error(f"Error sending order: {str(e)}")
            return False

    def clean_expired_orders(self, symbol: str):
        """Cancel orders that have been pending for too long"""
        try:
            if not self.verify_symbol(symbol):
                return
                
            orders = mt5.orders_get(symbol=symbol)
            if orders is None:
                return
                
            now = datetime.datetime.now()
            current_minutes = int((now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() / 60)
            
            for order in orders:
                try:
                    # Extract timestamp from order comment
                    if not order.comment or not order.comment.startswith("S"):
                        continue
                        
                    try:
                        # Parse minutes from comment (format: SXXXX where XXXX is minutes since midnight)
                        order_minutes = int(order.comment[1:])
                        
                        # Handle orders across midnight
                        if order_minutes > current_minutes:
                            order_age = (current_minutes + 1440 - order_minutes)  # 1440 = minutes in a day
                        else:
                            order_age = current_minutes - order_minutes
                        
                        if order_age > self.order_expiry_minutes:
                            request = {
                                "action": mt5.TRADE_ACTION_REMOVE,
                                "order": order.ticket,
                                "comment": "Expired order"
                            }
                            self.send_order(request)
                            logging.info(f"Cancelled expired order {order.ticket} for {symbol}, age: {order_age:.1f} minutes")
                            
                    except (ValueError, IndexError) as e:
                        logging.warning(f"Could not parse minutes from order comment: {order.comment}, Error: {str(e)}")
                        continue
                        
                except Exception as e:
                    logging.error(f"Error processing order {order.ticket}: {str(e)}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error cleaning expired orders for {symbol}: {str(e)}")

    def get_active_session(self) -> Tuple[str, Dict]:
        """Determine current active trading session"""
        now_utc = datetime.datetime.now(UTC)
        now_utc_time = now_utc.time()
        
        for session_name, session in sessions.items():
            if self.is_session_active(session["start"], session["end"], now_utc_time):
                return session_name, session
        return "No Active Session", None

    def is_session_active(self, start: datetime.time, end: datetime.time, current: datetime.time) -> bool:
        """Check if a session is currently active"""
        if start < end:
            return start <= current < end
        else:  # Session goes over midnight UTC
            return current >= start or current < end

    def get_positions_count(self, symbol: str, order_type: str) -> int:
        """Get count of active positions and pending orders for a symbol and type"""
        try:
            if not self.verify_symbol(symbol):
                return 0
                
            positions = mt5.positions_get(symbol=symbol)
            pending_orders = mt5.orders_get(symbol=symbol)
            
            total_count = 0
            
            if positions:
                for pos in positions:
                    if (order_type == "buy" and pos.type == mt5.POSITION_TYPE_BUY) or \
                       (order_type == "sell" and pos.type == mt5.POSITION_TYPE_SELL):
                        total_count += 1
            
            if pending_orders:
                for order in pending_orders:
                    if order_type == "buy" and order.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP]:
                        total_count += 1
                    elif order_type == "sell" and order.type in [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP]:
                        total_count += 1
            
            return total_count
            
        except Exception as e:
            logging.error(f"Error getting positions count for {symbol}: {str(e)}")
            return 0

    def get_30m_candle(self, symbol: str) -> Dict:
        """Get the last completed 30-minute candle"""
        try:
            if not self.verify_symbol(symbol):
                return None
                
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 2)
            if rates is None or len(rates) < 2:
                logging.error(f"Failed to get candle data for {symbol}")
                return None
                
            # Use index 1 for the last completed candle
            candle = rates[1]
            candle_range = abs(candle['high'] - candle['low'])
            
            return {
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "range": candle_range
            }
        except Exception as e:
            logging.error(f"Error getting candle data for {symbol}: {str(e)}")
            return None

    def calculate_daily_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Daily ATR (Average True Range)"""
        try:
            if not self.verify_symbol(symbol):
                return None

            # Get daily rates for ATR calculation
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, period + 1)
            if rates is None or len(rates) < period + 1:
                logging.error(f"Failed to get daily rates for ATR calculation for {symbol}")
                return None

            # Convert rates to pandas DataFrame
            df = pd.DataFrame(rates)
            
            # Calculate True Range
            df['high_low'] = df['high'] - df['low']
            df['high_close'] = abs(df['high'] - df['close'].shift(1))
            df['low_close'] = abs(df['low'] - df['close'].shift(1))
            
            df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
            
            # Calculate ATR
            atr = df['tr'].rolling(window=period).mean().iloc[-1]
            
            return atr
            
        except Exception as e:
            logging.error(f"Error calculating ATR for {symbol}: {str(e)}")
            return None

    def get_atr_based_stop_loss(self, symbol: str, entry_price: float, order_type: str, atr_multiplier: float = 1.0) -> float:
        """Calculate stop loss based on ATR"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return None
                
            # Get daily ATR
            atr = self.calculate_daily_atr(symbol)
            if not atr:
                return None
                
            # Calculate stop loss distance using ATR
            stop_distance = atr * atr_multiplier
            
            # Ensure minimum distance based on spread
            min_distance = symbol_info['spread'] * self.min_spread_multiplier
            stop_distance = max(stop_distance, min_distance)
            
            # Calculate stop loss price
            if order_type == "buy":
                stop_loss = round(entry_price - stop_distance, symbol_info['digits'])
            else:  # sell
                stop_loss = round(entry_price + stop_distance, symbol_info['digits'])
                
            return stop_loss
            
        except Exception as e:
            logging.error(f"Error calculating ATR-based stop loss for {symbol}: {str(e)}")
            return None

    def get_atr_based_take_profit(self, symbol: str, entry_price: float, order_type: str, atr_multiplier: float = 1.0) -> float:
        """Calculate take profit based on ATR"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return None
                
            # Get daily ATR
            atr = self.calculate_daily_atr(symbol)
            if not atr:
                return None
                
            # Calculate take profit distance using ATR
            tp_distance = atr * atr_multiplier
            
            # Calculate take profit price
            if order_type == "buy":
                take_profit = round(entry_price + tp_distance, symbol_info['digits'])
            else:  # sell
                take_profit = round(entry_price - tp_distance, symbol_info['digits'])
                
            return take_profit
            
        except Exception as e:
            logging.error(f"Error calculating ATR-based take profit for {symbol}: {str(e)}")
            return None

    def calculate_order_levels(self, symbol: str, current_price: float, order_type: str, candle: Dict) -> Tuple[float, float]:
        """Calculate scalping order levels based on current price and candle range"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return None, None
                
            pip_value = 0.0001 if not "JPY" in symbol else 0.01
            
            # Calculate minimum distance based on spread
            min_distance = symbol_info['spread'] * self.min_spread_multiplier
            
            # Use candle range for dynamic entry distances
            candle_range = candle['range']
            volatility_mult = 1.2 if "JPY" in symbol else 1.0
            
            # Scale entry distances based on candle range and volatility
            base_distance = max(
                self.base_entry_pips * pip_value,
                candle_range * 0.1  # 10% of candle range
            ) * volatility_mult * self.scalp_multiplier
            
            # Ensure distance is not smaller than minimum spread-based distance
            entry_distance = max(base_distance, min_distance)
            
            if order_type == "buy":
                limit_price = round(current_price - entry_distance, symbol_info['digits'])
                stop_price = round(current_price + entry_distance, symbol_info['digits'])
            else:  # sell
                limit_price = round(current_price + entry_distance, symbol_info['digits'])
                stop_price = round(current_price - entry_distance, symbol_info['digits'])
                
            return limit_price, stop_price
            
        except Exception as e:
            logging.error(f"Error calculating order levels for {symbol}: {str(e)}")
            return None, None

    def calculate_trailing_stop(self, symbol: str, candle: Dict, order_type: str, entry_price: float) -> float:
        """Calculate trailing stop based on last 30-minute candle range"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                return None
                
            candle_range = candle['range']
            pip_value = 0.0001 if not "JPY" in symbol else 0.01
            
            # Minimum trailing stop based on spread
            min_trailing_distance = symbol_info['spread'] * self.min_spread_multiplier
            
            # Calculate trailing stop distance
            base_trailing_distance = max(5 * pip_value, candle_range * 0.5)
            trailing_distance = max(base_trailing_distance, min_trailing_distance)
            
            if order_type == "buy":
                trailing_stop = round(entry_price - trailing_distance, symbol_info['digits'])
            else:  # sell
                trailing_stop = round(entry_price + trailing_distance, symbol_info['digits'])
                
            return trailing_stop
            
        except Exception as e:
            logging.error(f"Error calculating trailing stop for {symbol}: {str(e)}")
            return None

    def place_pending_orders(self, symbol: str, order_type: str):
        """Place pending orders for scalping"""
        try:
            if not self.verify_symbol(symbol):
                return
                
            # Clean expired orders first
            self.clean_expired_orders(symbol)
            
            current_positions = self.get_positions_count(symbol, order_type)
            
            if current_positions >= self.max_positions:
                logging.info(f"Maximum positions reached for {symbol} {order_type}")
                return
                
            # Get current price and candle data
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logging.error(f"Failed to get tick data for {symbol}")
                return
                
            current_price = tick.ask if order_type == "buy" else tick.bid
            candle = self.get_30m_candle(symbol)
            
            if not candle:
                logging.error(f"Failed to get candle data for {symbol}")
                return
                
            limit_price, stop_price = self.calculate_order_levels(symbol, current_price, order_type, candle)
            if not limit_price or not stop_price:
                return
            
            # Generate timestamp for order comments
            now = datetime.datetime.now()
            minutes_since_midnight = int((now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds() / 60)
            
            orders = []
            if order_type == "buy":
                # Calculate ATR-based stop losses and take profits
                limit_sl = self.get_atr_based_stop_loss(symbol, limit_price, "buy", atr_multiplier=0.30)
                stop_sl = self.get_atr_based_stop_loss(symbol, stop_price, "buy", atr_multiplier=0.30)
                limit_tp = self.get_atr_based_take_profit(symbol, limit_price, "buy", atr_multiplier=1.0)
                stop_tp = self.get_atr_based_take_profit(symbol, stop_price, "buy", atr_multiplier=1.0)
                
                if not all([limit_sl, stop_sl, limit_tp, stop_tp]):
                    logging.error(f"Failed to calculate SL/TP levels for {symbol}")
                    return
                
                # Buy Limit order
                buy_limit = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": self.volume,
                    "type": mt5.ORDER_TYPE_BUY_LIMIT,
                    "price": limit_price,
                    "sl": limit_sl,
                    "tp": limit_tp,
                    "deviation": 10,
                    "magic": 123456,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "comment": f"S{minutes_since_midnight}"
                }
                orders.append(buy_limit)
                
                # Buy Stop order
                buy_stop = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": self.volume,
                    "type": mt5.ORDER_TYPE_BUY_STOP,
                    "price": stop_price,
                    "sl": stop_sl,
                    "tp": stop_tp,
                    "deviation": 10,
                    "magic": 123456,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "comment": f"S{minutes_since_midnight}"
                }
                orders.append(buy_stop)
            else:
                # Calculate ATR-based stop losses and take profits
                limit_sl = self.get_atr_based_stop_loss(symbol, limit_price, "sell", atr_multiplier=0.30)
                stop_sl = self.get_atr_based_stop_loss(symbol, stop_price, "sell", atr_multiplier=0.30)
                limit_tp = self.get_atr_based_take_profit(symbol, limit_price, "sell", atr_multiplier=1.0)
                stop_tp = self.get_atr_based_take_profit(symbol, stop_price, "sell", atr_multiplier=1.0)
                
                if not all([limit_sl, stop_sl, limit_tp, stop_tp]):
                    logging.error(f"Failed to calculate SL/TP levels for {symbol}")
                    return
                
                # Sell Limit order
                sell_limit = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": self.volume,
                    "type": mt5.ORDER_TYPE_SELL_LIMIT,
                    "price": limit_price,
                    "sl": limit_sl,
                    "tp": limit_tp,
                    "deviation": 10,
                    "magic": 123456,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "comment": f"S{minutes_since_midnight}"
                }
                orders.append(sell_limit)
                
                # Sell Stop order
                sell_stop = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": self.volume,
                    "type": mt5.ORDER_TYPE_SELL_STOP,
                    "price": stop_price,
                    "sl": stop_sl,
                    "tp": stop_tp,
                    "deviation": 10,
                    "magic": 123456,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "comment": f"S{minutes_since_midnight}"
                }
                orders.append(sell_stop)

            # Send orders
            for order in orders:
                if self.get_positions_count(symbol, order_type) < self.max_positions:
                    self.send_order(order)
                    
        except Exception as e:
            logging.error(f"Error placing orders for {symbol}: {str(e)}")

    def manage_session_orders(self):
        """Manage orders for current session"""
        try:
            session_name, session = self.get_active_session()
            
            if session is None:
                logging.info("No active trading session")
                return
                
            logging.info(f"Managing orders for {session_name} session")
            
            # Process buy pairs
            for symbol in session["buy_pairs"]:
                self.place_pending_orders(symbol, "buy")
                
            # Process sell pairs
            for symbol in session["sell_pairs"]:
                self.place_pending_orders(symbol, "sell")
                
        except Exception as e:
            logging.error(f"Error managing session orders: {str(e)}")

    def run(self):
        """Main bot loop"""
        logging.info("Starting Market Session Trading Bot...")
        
        try:
            self.initialize_mt5()
            
            while True:
                if not self.initialized:
                    logging.error("MT5 not initialized, attempting to reconnect...")
                    try:
                        self.initialize_mt5()
                        time.sleep(5)  # Wait before retrying
                        continue
                    except:
                        time.sleep(30)  # Wait longer before next retry
                        continue
                
                try:
                    self.manage_session_orders()
                except Exception as e:
                    logging.error(f"Error in main loop: {str(e)}")
                
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
        finally:
            if self.initialized:
                mt5.shutdown()
                logging.info("MT5 connection closed")

if __name__ == "__main__":
    trader = MarketSessionTrader()
    trader.run() 