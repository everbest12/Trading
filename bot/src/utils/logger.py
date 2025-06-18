import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional
import sys

def setup_logger(
    name: str, 
    log_file: Optional[str] = None, 
    level: int = logging.INFO,
    console_output: bool = True,
    max_file_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up and configure a logger.
    
    Args:
        name: Logger name
        log_file: Path to log file (optional)
        level: Logging level
        console_output: Whether to output logs to console
        max_file_size_mb: Maximum size of log files in MB
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler if requested
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Add file handler if log_file is provided
    if log_file:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_strategy_logger(
    strategy_name: str, 
    symbol: str, 
    timeframe: str
) -> logging.Logger:
    """
    Get a logger specifically for a trading strategy.
    
    Args:
        strategy_name: Name of the strategy
        symbol: Trading symbol
        timeframe: Trading timeframe
        
    Returns:
        Configured logger instance
    """
    logger_name = f"{strategy_name}_{symbol}_{timeframe}"
    log_file = f"logs/trades/{logger_name}.log"
    
    return setup_logger(
        name=logger_name,
        log_file=log_file,
        level=logging.INFO,
        console_output=True
    )

def get_error_logger() -> logging.Logger:
    """
    Get a logger specifically for error logging.
    
    Returns:
        Configured logger instance
    """
    return setup_logger(
        name="error_logger",
        log_file="logs/errors/error.log",
        level=logging.ERROR,
        console_output=True
    )

def get_performance_logger() -> logging.Logger:
    """
    Get a logger specifically for performance metrics.
    
    Returns:
        Configured logger instance
    """
    return setup_logger(
        name="performance_logger",
        log_file="logs/performance/performance.log",
        level=logging.INFO,
        console_output=False
    )

# Example usage
if __name__ == "__main__":
    # Basic logger
    logger = setup_logger("test_logger", "logs/test.log")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Strategy logger
    strategy_logger = get_strategy_logger("rsi", "EURUSD", "H1")
    strategy_logger.info("RSI strategy initialized")
    
    # Error logger
    error_logger = get_error_logger()
    error_logger.error("An error occurred: connection refused") 