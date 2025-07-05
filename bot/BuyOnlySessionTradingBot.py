import MetaTrader5 as mt5
import pandas as pd
import time
import datetime
import pytz
from datetime import UTC
import logging


#Place buy limit and buy stop orders only bot, every 1 minutes and use the last 30 minutes candle for stop loss.  
#If the price is above the buy limit, cancel the buy limit and place a buy stop order.
#If the price is below the buy stop, cancel the buy stop and place a buy limit order.
# 




# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_sessions.log')
    ]
)

# Define sessions (UTC time)
sessions = {
    "Tokyo & Sydney": {  # UTC+9/UTC+10
        "start": datetime.time(22, 0),  # 22:00 UTC (07:00 Tokyo next day)
        "end": datetime.time(7, 0),    # 07:00 UTC (16:00 Tokyo)
        "symbols": [
            "USDJPY", "AUDJPY", "NZDUSD", "EURAUD",  # Major JPY and AUD pairs
            "AUDUSD", "AUDNZD", "AUDCAD",  # Additional AUD crosses
            "NZDJPY", "NZDCHF",  # Additional NZD crosses
            "JPYCHF", "JPYCAD"   # Additional JPY crosses
        ]
    },
    "London": {  # UTC+0/+1
        "start": datetime.time(7, 0),   # 07:00 UTC (08:00 London)
        "end": datetime.time(16, 0),    # 16:00 UTC (17:00 London)
        "symbols": [
            "GBPUSD", "EURCHF", "USDCHF", "GBPJPY",  # Major GBP and CHF pairs
            "EURGBP", "EURUSD", "GBPCHF",  # Additional EUR and GBP crosses
            "EURJPY", "EURCAD",  # Additional EUR crosses
            "CHFJPY", "CHFCAD"   # Additional CHF crosses
        ]
    },
    "New York": {  # UTC-4
        "start": datetime.time(13, 0),  # 13:00 UTC (09:00 NY)
        "end": datetime.time(22, 0),    # 22:00 UTC (18:00 NY)
        "symbols": [
            "EURUSD", "USDCAD", "XAUUSD", "EURCAD",  # Major USD and CAD pairs
            "USDJPY", "USDCHF", "USDSGD",  # Additional USD crosses
            "CADJPY", "CADCHF",  # Additional CAD crosses
            "XAUJPY", "XAUCHF"   # Additional Gold crosses
        ]
    }
}

def is_session_active(session_start, session_end, current_time):
    """Helper function to determine if a session is active"""
    if session_start < session_end:
        return session_start <= current_time < session_end
    else:  # Session goes over midnight UTC
        return current_time >= session_start or current_time < session_end

# Connect to MT5
def initialize_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"Initialize() failed: {mt5.last_error()}")
    logging.info("MT5 initialized successfully")

# Determine active session
def get_active_symbols():
    # Get current time in UTC
    now_utc = datetime.datetime.now(UTC)
    now_utc_time = now_utc.time()
    
    # Also get time in major financial centers for logging
    timezone_info = {
        'UTC': now_utc,
        'New York': now_utc.astimezone(pytz.timezone('America/New_York')),
        'London': now_utc.astimezone(pytz.timezone('Europe/London')),
        'Tokyo': now_utc.astimezone(pytz.timezone('Asia/Tokyo')),
        'Sydney': now_utc.astimezone(pytz.timezone('Australia/Sydney'))
    }
    
    # Log current times in different zones
    time_str = "Current times:\n"
    for zone, time in timezone_info.items():
        time_str += f"{zone}: {time.strftime('%H:%M:%S')}\n"
    logging.info(time_str)

    active_symbols = []
    active_sessions = []

    for session_name, session in sessions.items():
        if is_session_active(session["start"], session["end"], now_utc_time):
            active_symbols.extend(session["symbols"])
            active_sessions.append(session_name)
            logging.info(f"Session {session_name} is active - Start: {session['start']}, End: {session['end']} UTC")

    if active_sessions:
        logging.info(f"Active trading sessions: {', '.join(active_sessions)}")
        logging.info(f"Active currency pairs: {', '.join(set(active_symbols))}")
    else:
        logging.warning("No active trading sessions at this time")

    return list(set(active_symbols))

# Get current 30-minute candle
def get_30m_candle(symbol):
    """Get the last completed 30-minute candle."""
    # Get the last 2 candles - index 1 will be the last completed candle
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 2)
    if rates is None or len(rates) < 2:
        logging.error(f"Failed to get candle data for {symbol}")
        return None
        
    # Use index 1 for the last completed candle
    candle = rates[1]
    logging.debug(f"Retrieved last completed 30m candle for {symbol} - High: {candle['high']}, Low: {candle['low']}, Close: {candle['close']}")
    
    # Add timestamp info for verification
    candle_time = datetime.datetime.fromtimestamp(candle['time'])
    logging.info(f"Using 30m candle from {candle_time} for {symbol}")
    
    return {
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "time": candle_time
    }

def get_pending_orders(symbol):
    """Get only pending (not active) orders for a symbol."""
    orders = mt5.orders_get(symbol=symbol)
    if orders is None:
        return []
    # Filter only for pending buy limit and buy stop orders
    # STATE_STARTED means the order is pending and not yet triggered
    return [order for order in orders 
            if order.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] 
            and order.state == mt5.ORDER_STATE_STARTED]

def cancel_pending_order(ticket):
    """Cancel a specific pending order by ticket number."""
    # First verify this is actually a pending order before canceling
    order = mt5.orders_get(ticket=ticket)
    if not order or len(order) == 0:
        logging.warning(f"Order {ticket} not found")
        return False
        
    order = order[0]
    # Only cancel if it's a pending order (not executed)
    if order.state != mt5.ORDER_STATE_STARTED:
        logging.warning(f"Order {ticket} is not in pending state")
        return False
        
    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
        "comment": "Pending order cancelled by bot"
    }
    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE

def cancel_all_pending_orders(symbol):
    """Cancel all pending (not executed) orders for a symbol."""
    orders = get_pending_orders(symbol)
    cancelled_count = 0
    for order in orders:
        if cancel_pending_order(order.ticket):
            logging.info(f"Cancelled pending order {order.ticket} for {symbol}")
            cancelled_count += 1
        else:
            logging.error(f"Failed to cancel pending order {order.ticket} for {symbol}")
    if cancelled_count > 0:
        logging.info(f"Cancelled {cancelled_count} pending orders for {symbol}")

def get_pip_value(symbol):
    """Get the pip value for a symbol."""
    if symbol.startswith("XAU"):  # Gold
        return 0.1  # Gold is quoted with 2 decimal places
    return 0.0001  # Most forex pairs use 4 decimal places except JPY pairs

def get_session_volatility_multiplier(session_name):
    """Get volatility multiplier based on session."""
    multipliers = {
        "Tokyo & Sydney": 0.8,  # Generally lower volatility
        "London": 1.2,          # Higher volatility
        "New York": 1.0         # Base volatility
    }
    return multipliers.get(session_name, 1.0)

def get_pair_volatility_multiplier(symbol):
    """Get volatility multiplier based on currency pair."""
    # Define base pip distances for different pair types
    if symbol.startswith("XAU"):  # Gold pairs
        return 1.5
    elif "JPY" in symbol:  # JPY pairs
        return 1.2
    elif any(major in symbol for major in ["EUR", "GBP", "USD"]):  # Major pairs
        return 1.0
    else:  # Cross pairs
        return 1.1

def calculate_order_distances(symbol, current_session):
    """Calculate pip distances for orders based on pair and session."""
    base_limit_pips = 5  # Base distance for limit order
    base_stop_pips = 5   # Base distance for stop order
    
    # Get multipliers
    session_mult = get_session_volatility_multiplier(current_session)
    pair_mult = get_pair_volatility_multiplier(symbol)
    
    # Calculate final distances
    limit_pips = base_limit_pips * session_mult * pair_mult
    stop_pips = base_stop_pips * session_mult * pair_mult
    
    # Convert pips to price movement
    pip_value = get_pip_value(symbol)
    limit_distance = round(limit_pips * pip_value, 5)
    stop_distance = round(stop_pips * pip_value, 5)
    
    return limit_distance, stop_distance

def get_current_session():
    """Determine the current active trading session."""
    now_utc = datetime.datetime.now(UTC)
    now_utc_time = now_utc.time()
    
    for session_name, session in sessions.items():
        if is_session_active(session["start"], session["end"], now_utc_time):
            return session_name
    return "No Active Session"

def calculate_trailing_stop(symbol, candle, order_type, entry_price):
    """Calculate trailing stop based on last closed candle range."""
    candle_range = abs(candle["high"] - candle["low"])
    
    # For buy orders, trailing stop is below entry
    if order_type == mt5.ORDER_TYPE_BUY_LIMIT or order_type == mt5.ORDER_TYPE_BUY_STOP:
        trailing_stop = round(entry_price - candle_range, 5)
        
    # Adjust for gold pairs
    if symbol.startswith("XAU"):
        trailing_stop = round(trailing_stop, 3)
        
    return trailing_stop

def place_orders(symbol):
    """Place buy limit and buy stop orders based on current price."""
    # Get the 30-minute candle data
    candle = get_30m_candle(symbol)
    if not candle:
        logging.error(f"Could not get candle for {symbol}")
        return

    # Get current price and calculate ranges
    current_price = mt5.symbol_info_tick(symbol).ask
    volume = 0.1  # Modify as needed

    # Get current session and calculate order distances
    current_session = get_current_session()
    limit_distance, stop_distance = calculate_order_distances(symbol, current_session)

    # Cancel only pending orders, leaving active positions untouched
    cancel_all_pending_orders(symbol)

    # Define the limit and stop levels using calculated distances
    limit_price = round(current_price - limit_distance, 5)
    stop_price = round(current_price + stop_distance, 5)

    logging.info(f"Current price for {symbol}: {current_price}")
    logging.info(f"Session: {current_session}, Limit distance: {limit_distance}, Stop distance: {stop_distance}")
    logging.info(f"Buy limit level: {limit_price} ({round(limit_distance/get_pip_value(symbol), 1)} pips)")
    logging.info(f"Buy stop level: {stop_price} ({round(stop_distance/get_pip_value(symbol), 1)} pips)")
    logging.info(f"Using candle range for trailing stop: {abs(candle['high'] - candle['low'])}")

    # Place both buy limit and buy stop orders
    orders = []

    # Buy Limit order
    buy_limit = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": limit_price,
        "sl": calculate_trailing_stop(symbol, candle, mt5.ORDER_TYPE_BUY_LIMIT, limit_price),
        "tp": 0.0,  # No take profit, using trailing stop only
        "deviation": 10,
        "magic": 123456,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": f"Buy limit by bot {current_session} with trailing stop"
    }
    orders.append(buy_limit)

    # Buy Stop order
    buy_stop = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_STOP,
        "price": stop_price,
        "sl": calculate_trailing_stop(symbol, candle, mt5.ORDER_TYPE_BUY_STOP, stop_price),
        "tp": 0.0,  # No take profit, using trailing stop only
        "deviation": 10,
        "magic": 123456,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": f"Buy stop by bot {current_session} with trailing stop"
    }
    orders.append(buy_stop)

    # Adjust orders for gold pairs
    if symbol.startswith("XAU"):
        for order in orders:
            for key in ["price", "sl"]:  # Removed 'tp' since we're not using it
                order[key] = round(order[key], 3)

    # Send the orders
    for order in orders:
        result = mt5.order_send(order)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Failed to send {order['type']} order on {symbol}: {result.retcode}")
        else:
            logging.info(f"Successfully placed {order['type']} order for {symbol} at {order['price']} with trailing stop at {order['sl']}")

# Main loop
def run_bot():
    logging.info("Starting trading bot...")
    initialize_mt5()
    try:
        while True:
            active_symbols = get_active_symbols()
            if active_symbols:
                logging.info("Starting order placement cycle...")
                for symbol in active_symbols:
                    place_orders(symbol)
                logging.info("Completed order placement cycle")
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
    finally:
        mt5.shutdown()
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    run_bot()
