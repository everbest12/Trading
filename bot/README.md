# Algorithmic Trading Bot Platform

A comprehensive algorithmic trading platform designed for Forex, cryptocurrency, commodity and equities markets. The platform features multiple strategy types, real-time monitoring, and risk management capabilities.

## Features

- **Multiple Strategy Types**:
  - **News/Event-Based Trading Bots**: Trade based on market-moving news and economic events
  - **Market Session Scalping Bots**: Exploit patterns during specific market sessions (London, New York, etc.)
  - **Day Trading Bots**: Capture intraday price movements with advanced technical indicators

- **Advanced Architecture**:
  - Modular, reusable code structure
  - Low-latency execution framework
  - Multiple broker/exchange integrations
  - Real-time monitoring and analytics

- **Risk Management**:
  - Dynamic position sizing
  - Automated stop-loss mechanisms
  - Daily drawdown limits
  - Session-based risk controls

- **Visualization & Monitoring**:
  - Real-time performance dashboard
  - Trade logs and history tracking
  - Position monitoring
  - P&L reporting

## System Architecture

```
bot/
├── config/                 # Configuration files
├── data/                   # Market data storage
├── docs/                   # Documentation
├── logs/                   # Log files
├── notebooks/              # Jupyter notebooks for research
├── scripts/                # Utility scripts
├── src/                    # Source code
│   ├── backtesting/        # Backtesting framework
│   ├── brokers/            # Broker API connectors
│   ├── dashboard/          # Monitoring dashboards
│   ├── indicators/         # Technical indicators
│   ├── llm/                # LLM integration
│   ├── risk_management/    # Risk management modules
│   ├── strategies/         # Trading strategies
│   │   ├── day_trading/    # Day trading strategies
│   │   ├── event_driven/   # Event-driven strategies
│   │   ├── session_based/  # Session-based strategies
│   │   └── technical/      # Technical analysis strategies
│   └── utils/              # Utility functions
├── tests/                  # Test cases
└── ui/                     # User interface
```

## Available Trading Strategies

### 1. News Impact Strategy
A strategy that trades based on economic news releases and events. It monitors news feeds, reacts to high-impact events, and positions the portfolio to take advantage of the volatility that follows market-moving news.

### 2. London Breakout Strategy
This strategy trades the volatility breakout that often occurs at the start of the London trading session. It identifies the price range during the pre-London hours and places orders to catch the breakout when London opens.

### 3. VWAP Reversion Strategy
A day trading strategy that trades mean reversion to the Volume Weighted Average Price (VWAP) for liquid equities. It identifies when prices deviate significantly from VWAP and enters positions expecting a reversion to the mean.

### 4. RSI Strategy
A technical analysis strategy that uses the Relative Strength Index (RSI) indicator to identify overbought and oversold conditions in the market, generating signals when the RSI crosses specific thresholds.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- MetaTrader 5 (for Forex trading)
- Binance API keys (for cryptocurrency trading)
- Interactive Brokers account (for equities trading)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/trading-bot.git
cd trading-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your broker connections in the `config/brokers/` directory.

4. Set up trading parameters in `config/trading_params.json`.

### Running a Strategy

```bash
python src/main.py rsi --symbol EURUSD --timeframe H1 --risk-percent 1.0
```

```bash
python src/main.py news --impact-threshold 0.7 --risk-percent 0.5
```

```bash
python src/main.py london --symbols EURUSD,GBPUSD --range-hours 3
```

```bash
python src/main.py vwap --symbols AAPL,MSFT --vwap-deviation 1.5
```

### Running the Dashboard

```bash
streamlit run src/dashboard/bot_dashboard.py
```

## Risk Warning

Trading financial instruments carries a high level of risk and may not be suitable for all investors. Before deciding to trade, you should carefully consider your investment objectives, level of experience, and risk appetite. The possibility exists that you could sustain a loss of some or all of your initial investment and therefore you should not invest money that you cannot afford to lose.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors who have helped develop and test this platform
- Special thanks to the open-source trading community for insights and inspiration

| Session | Start (UTC) | End (UTC) | Major Pairs | Additional Pairs |
|---------|-------------|-----------|-------------|------------------|
| Tokyo & Sydney | 12:00 | 21:00 | USDJPY, AUDJPY, NZDUSD, EURAUD | AUDUSD, AUDNZD, AUDCAD, NZDJPY, NZDCHF |
| London | 07:00 | 16:00 | GBPUSD, EURCHF, USDCHF, GBPJPY | EURGBP, EURUSD, GBPCHF, EURJPY, EURCAD |
| New York | 21:00 | 08:00 | EURUSD, USDCAD, XAUUSD, EURCAD | USDJPY, USDCHF, USDSGD, CADJPY, CADCHF |
