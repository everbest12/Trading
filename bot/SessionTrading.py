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
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 1)
    if rates is None or len(rates) == 0:
        logging.error(f"Failed to get candle data for {symbol}")
        return None
    candle = rates[0]
    logging.debug(f"Retrieved 30m candle for {symbol} - High: {candle['high']}, Low: {candle['low']}, Close: {candle['close']}")
    return {
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"]
    }

# Place buy limit and buy stop orders
def place_orders(symbol):
    candle = get_30m_candle(symbol)
    if not candle:
        logging.error(f"Could not get candle for {symbol}")
        return

    price = mt5.symbol_info_tick(symbol).ask
    sl_range = abs(candle["high"] - candle["low"])
    volume = 0.1  # Modify as needed

    logging.info(f"Attempting to place orders for {symbol} at current price {price}")

    # Buy Limit below price
    buy_limit = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": round(price - 0.0010, 5),
        "sl": round(price - 0.0010 - sl_range, 5),
        "tp": round(price + 0.0015, 5),
        "deviation": 10,
        "magic": 123456,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": "Buy limit by bot"
    }

    # Buy Stop above price
    buy_stop = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_STOP,
        "price": round(price + 0.0010, 5),
        "sl": round(price + 0.0010 - sl_range, 5),
        "tp": round(price + 0.0015, 5),
        "deviation": 10,
        "magic": 123456,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        "comment": "Buy stop by bot"
    }

    for order in [buy_limit, buy_stop]:
        result = mt5.order_send(order)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Failed to send {order['type']} order on {symbol}: {result.retcode}")
        else:
            logging.info(f"Successfully placed {order['type']} order for {symbol} at {order['price']}")

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
