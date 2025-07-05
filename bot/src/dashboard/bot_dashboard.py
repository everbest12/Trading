#!/usr/bin/env python3
"""
Bot Dashboard

This dashboard provides real-time monitoring and analytics for the trading bots.
It displays bot status, performance metrics, open positions, and trade history.
"""

import os
import sys
import json
from datetime import datetime, timedelta
import time
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from src.utils.logger import setup_logger

logger = setup_logger("dashboard", "logs/dashboard.log")

# Dashboard configuration
st.set_page_config(
    page_title="Trading Bot Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .reportview-container {
        background-color: #0e1117;
    }
    .sidebar .sidebar-content {
        background-color: #262730;
    }
    .metric-card {
        border: 1px solid #4B5563;
        border-radius: 0.5rem;
        padding: 1rem;
        background-color: #1F2937;
    }
    .profit {
        color: #10B981;
    }
    .loss {
        color: #EF4444;
    }
</style>
""", unsafe_allow_html=True)

def load_config(config_path):
    """Load configuration from file."""
    try:
        with open(config_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return {}

def load_logs(log_path, max_lines=1000):
    """Load and parse log files."""
    try:
        if not os.path.exists(log_path):
            return []
            
        with open(log_path, 'r') as file:
            lines = file.readlines()[-max_lines:]
            
        log_entries = []
        
        for line in lines:
            try:
                parts = line.strip().split(" | ")
                if len(parts) >= 3:
                    timestamp_str = parts[0]
                    level = parts[1]
                    message = " | ".join(parts[2:])
                    
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        timestamp = datetime.now()
                    
                    log_entries.append({
                        "timestamp": timestamp,
                        "level": level,
                        "message": message
                    })
            except:
                continue
                
        return log_entries
    except Exception as e:
        logger.error(f"Error loading logs: {str(e)}")
        return []

def load_trade_history(file_path):
    """Load trade history from CSV file."""
    try:
        if not os.path.exists(file_path):
            return pd.DataFrame()
            
        df = pd.read_csv(file_path)
        
        # Convert timestamp to datetime
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
        return df
    except Exception as e:
        logger.error(f"Error loading trade history: {str(e)}")
        return pd.DataFrame()

def get_bot_status():
    """Get the current status of all running bots."""
    status = []
    
    bot_status_path = "logs/bot_status.json"
    
    try:
        if os.path.exists(bot_status_path):
            with open(bot_status_path, 'r') as file:
                status_data = json.load(file)
                
            for bot_id, bot_data in status_data.items():
                # Check if the bot has updated its status recently (within 5 minutes)
                last_update = datetime.fromisoformat(bot_data.get("last_update", "2000-01-01T00:00:00"))
                is_active = (datetime.now() - last_update).total_seconds() < 300
                
                status.append({
                    "bot_id": bot_id,
                    "strategy": bot_data.get("strategy", "unknown"),
                    "symbol": bot_data.get("symbol", "unknown"),
                    "active": is_active,
                    "last_update": last_update,
                    "daily_pnl": bot_data.get("daily_pnl", 0),
                    "total_pnl": bot_data.get("total_pnl", 0),
                    "win_rate": bot_data.get("win_rate", 0),
                    "trades_today": bot_data.get("trades_today", 0),
                    "total_trades": bot_data.get("total_trades", 0),
                    "open_positions": bot_data.get("open_positions", 0)
                })
                
        return status
    except Exception as e:
        logger.error(f"Error getting bot status: {str(e)}")
        return []

def get_open_positions():
    """Get all open positions across all bots."""
    positions = []
    
    positions_path = "logs/open_positions.json"
    
    try:
        if os.path.exists(positions_path):
            with open(positions_path, 'r') as file:
                positions_data = json.load(file)
                
            for position in positions_data:
                # Convert timestamp to datetime
                if "open_time" in position:
                    position["open_time"] = datetime.fromisoformat(position["open_time"])
                    
                positions.append(position)
                
        return positions
    except Exception as e:
        logger.error(f"Error getting open positions: {str(e)}")
        return []

def render_sidebar():
    """Render the sidebar with filtering options."""
    st.sidebar.title("Trading Bot Dashboard")
    
    # Get bot status for filtering
    bot_status = get_bot_status()
    strategies = sorted(list(set([bot["strategy"] for bot in bot_status])))
    symbols = sorted(list(set([bot["symbol"] for bot in bot_status])))
    
    # Filters
    st.sidebar.header("Filters")
    
    selected_strategies = st.sidebar.multiselect(
        "Strategies",
        options=strategies,
        default=strategies
    )
    
    selected_symbols = st.sidebar.multiselect(
        "Symbols",
        options=symbols,
        default=symbols
    )
    
    show_inactive = st.sidebar.checkbox("Show Inactive Bots", value=False)
    
    # Date range filter
    st.sidebar.header("Date Range")
    
    today = datetime.now().date()
    start_date = st.sidebar.date_input(
        "Start Date",
        value=today - timedelta(days=7)
    )
    
    end_date = st.sidebar.date_input(
        "End Date",
        value=today
    )
    
    # Refresh interval
    st.sidebar.header("Settings")
    
    refresh_interval = st.sidebar.slider(
        "Refresh Interval (seconds)",
        min_value=5,
        max_value=60,
        value=30,
        step=5
    )
    
    # About section
    st.sidebar.header("About")
    st.sidebar.info(
        """
        This dashboard provides real-time monitoring and analytics for the trading bots.
        
        Data is refreshed automatically every few seconds to provide the most up-to-date information.
        """
    )
    
    return {
        "selected_strategies": selected_strategies,
        "selected_symbols": selected_symbols,
        "show_inactive": show_inactive,
        "start_date": start_date,
        "end_date": end_date,
        "refresh_interval": refresh_interval
    }

def render_overview(filters):
    """Render the overview section with key metrics."""
    st.header("Trading Bot Overview")
    
    # Get bot status
    bot_status = get_bot_status()
    
    # Apply filters
    filtered_bots = []
    for bot in bot_status:
        if bot["strategy"] in filters["selected_strategies"] and bot["symbol"] in filters["selected_symbols"]:
            if bot["active"] or filters["show_inactive"]:
                filtered_bots.append(bot)
    
    # Calculate summary metrics
    total_pnl = sum([bot["total_pnl"] for bot in filtered_bots])
    daily_pnl = sum([bot["daily_pnl"] for bot in filtered_bots])
    total_trades = sum([bot["total_trades"] for bot in filtered_bots])
    trades_today = sum([bot["trades_today"] for bot in filtered_bots])
    open_positions = sum([bot["open_positions"] for bot in filtered_bots])
    active_bots = sum([1 for bot in filtered_bots if bot["active"]])
    
    avg_win_rate = 0
    if filtered_bots:
        avg_win_rate = sum([bot["win_rate"] for bot in filtered_bots]) / len(filtered_bots)
    
    # Display summary metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total P&L",
            value=f"${total_pnl:,.2f}",
            delta=f"${daily_pnl:,.2f} Today"
        )
        
    with col2:
        st.metric(
            label="Active Bots",
            value=f"{active_bots}",
            delta=f"{len(filtered_bots) - active_bots} Inactive" if len(filtered_bots) - active_bots > 0 else None
        )
        
    with col3:
        st.metric(
            label="Open Positions",
            value=f"{open_positions}",
            delta=None
        )
        
    with col4:
        st.metric(
            label="Avg Win Rate",
            value=f"{avg_win_rate:.1f}%",
            delta=None
        )
    
    # Display bot status table
    st.subheader("Bot Status")
    
    if filtered_bots:
        bot_df = pd.DataFrame(filtered_bots)
        
        # Format columns
        if not bot_df.empty:
            bot_df["daily_pnl"] = bot_df["daily_pnl"].apply(lambda x: f"${x:,.2f}")
            bot_df["total_pnl"] = bot_df["total_pnl"].apply(lambda x: f"${x:,.2f}")
            bot_df["win_rate"] = bot_df["win_rate"].apply(lambda x: f"{x:.1f}%")
            bot_df["last_update"] = bot_df["last_update"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            bot_df["status"] = bot_df["active"].apply(lambda x: "🟢 Active" if x else "🔴 Inactive")
            
            # Reorder and select columns
            display_df = bot_df[["bot_id", "strategy", "symbol", "status", "daily_pnl", "total_pnl", 
                                "win_rate", "trades_today", "total_trades", "open_positions", "last_update"]]
            
            display_df.columns = ["Bot ID", "Strategy", "Symbol", "Status", "Daily P&L", "Total P&L", 
                                 "Win Rate", "Trades Today", "Total Trades", "Open Positions", "Last Update"]
            
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No bots found matching the selected filters")

def render_performance_charts(filters):
    """Render performance charts."""
    st.header("Performance Analysis")
    
    # Load trade history
    trade_history = load_trade_history("logs/trade_history.csv")
    
    if trade_history.empty:
        st.info("No trade history data available")
        return
    
    # Apply filters
    filtered_history = trade_history[
        (trade_history["strategy"].isin(filters["selected_strategies"])) &
        (trade_history["symbol"].isin(filters["selected_symbols"])) &
        (trade_history["timestamp"].dt.date >= filters["start_date"]) &
        (trade_history["timestamp"].dt.date <= filters["end_date"])
    ]
    
    if filtered_history.empty:
        st.info("No trade data available for the selected filters")
        return
    
    # Create two columns for charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Cumulative P&L")
        
        # Calculate cumulative P&L
        filtered_history = filtered_history.sort_values("timestamp")
        filtered_history["cumulative_pnl"] = filtered_history["profit"].cumsum()
        
        # Create chart
        fig = px.line(
            filtered_history,
            x="timestamp",
            y="cumulative_pnl",
            title="Cumulative P&L Over Time",
            labels={"cumulative_pnl": "Cumulative P&L ($)", "timestamp": "Date"}
        )
        
        # Customize layout
        fig.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("P&L by Strategy")
        
        # Aggregate profit by strategy
        strategy_pnl = filtered_history.groupby("strategy")["profit"].sum().reset_index()
        
        # Create chart
        fig = px.bar(
            strategy_pnl,
            x="strategy",
            y="profit",
            title="P&L by Strategy",
            labels={"profit": "P&L ($)", "strategy": "Strategy"},
            color="profit",
            color_continuous_scale=["#EF4444", "#10B981"]
        )
        
        # Customize layout
        fig.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            coloraxis_showscale=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Additional charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Win/Loss Ratio")
        
        # Calculate win/loss counts
        win_count = len(filtered_history[filtered_history["profit"] > 0])
        loss_count = len(filtered_history[filtered_history["profit"] < 0])
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=["Winning Trades", "Losing Trades"],
            values=[win_count, loss_count],
            hole=.4,
            marker_colors=["#10B981", "#EF4444"]
        )])
        
        # Customize layout
        fig.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            annotations=[dict(text=f"{win_count + loss_count}<br>Trades", x=0.5, y=0.5, font_size=20, showarrow=False)]
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("P&L by Symbol")
        
        # Aggregate profit by symbol
        symbol_pnl = filtered_history.groupby("symbol")["profit"].sum().reset_index()
        
        # Create chart
        fig = px.bar(
            symbol_pnl,
            x="symbol",
            y="profit",
            title="P&L by Symbol",
            labels={"profit": "P&L ($)", "symbol": "Symbol"},
            color="profit",
            color_continuous_scale=["#EF4444", "#10B981"]
        )
        
        # Customize layout
        fig.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            coloraxis_showscale=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Trade details
    st.subheader("Recent Trades")
    
    if not filtered_history.empty:
        # Sort by timestamp
        recent_trades = filtered_history.sort_values("timestamp", ascending=False).head(50)
        
        # Format columns
        recent_trades["profit"] = recent_trades["profit"].apply(lambda x: f"${x:,.2f}")
        recent_trades["timestamp"] = recent_trades["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Select and rename columns
        display_df = recent_trades[["timestamp", "strategy", "symbol", "action", "price", "size", "profit"]]
        display_df.columns = ["Timestamp", "Strategy", "Symbol", "Action", "Price", "Size", "Profit"]
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No recent trades available")

def render_open_positions(filters):
    """Render open positions table and charts."""
    st.header("Open Positions")
    
    # Get open positions
    positions = get_open_positions()
    
    # Apply filters
    filtered_positions = []
    for position in positions:
        if position.get("strategy", "") in filters["selected_strategies"] and position.get("symbol", "") in filters["selected_symbols"]:
            filtered_positions.append(position)
    
    if filtered_positions:
        # Create DataFrame
        positions_df = pd.DataFrame(filtered_positions)
        
        # Format columns
        positions_df["current_profit"] = positions_df["current_profit"].apply(lambda x: f"${x:,.2f}")
        positions_df["open_price"] = positions_df["open_price"].apply(lambda x: f"${x:,.5f}")
        positions_df["current_price"] = positions_df["current_price"].apply(lambda x: f"${x:,.5f}")
        
        if "open_time" in positions_df.columns:
            positions_df["open_time"] = positions_df["open_time"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Select and rename columns
        display_df = positions_df[["bot_id", "strategy", "symbol", "type", "size", "open_price", 
                                  "current_price", "current_profit", "open_time"]]
        
        display_df.columns = ["Bot ID", "Strategy", "Symbol", "Type", "Size", "Open Price", 
                             "Current Price", "Current P&L", "Open Time"]
        
        st.dataframe(display_df, use_container_width=True)
        
        # Position summary
        st.subheader("Position Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Count by strategy
            strategy_counts = positions_df["strategy"].value_counts().reset_index()
            strategy_counts.columns = ["Strategy", "Count"]
            
            fig = px.pie(
                strategy_counts,
                values="Count",
                names="Strategy",
                title="Open Positions by Strategy"
            )
            
            fig.update_layout(
                height=300,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Count by symbol
            symbol_counts = positions_df["symbol"].value_counts().reset_index()
            symbol_counts.columns = ["Symbol", "Count"]
            
            fig = px.pie(
                symbol_counts,
                values="Count",
                names="Symbol",
                title="Open Positions by Symbol"
            )
            
            fig.update_layout(
                height=300,
                margin=dict(l=40, r=40, t=40, b=40)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No open positions found matching the selected filters")

def render_log_viewer(filters):
    """Render log viewer with filtering."""
    st.header("Log Viewer")
    
    # Create tabs for different log types
    log_tabs = st.tabs(["Main Logs", "Strategy Logs", "Error Logs"])
    
    # Main logs
    with log_tabs[0]:
        main_logs = load_logs("logs/main.log")
        
        if main_logs:
            # Create DataFrame
            logs_df = pd.DataFrame(main_logs)
            
            # Format columns
            logs_df["timestamp"] = logs_df["timestamp"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Apply date filter
            logs_df["date"] = pd.to_datetime(logs_df["timestamp"]).dt.date
            filtered_logs = logs_df[
                (logs_df["date"] >= filters["start_date"]) &
                (logs_df["date"] <= filters["end_date"])
            ]
            
            if not filtered_logs.empty:
                st.dataframe(filtered_logs[["timestamp", "level", "message"]], use_container_width=True)
            else:
                st.info("No logs found for the selected date range")
        else:
            st.info("No main logs available")
    
    # Strategy logs
    with log_tabs[1]:
        strategy_logs = []
        
        # Load logs for selected strategies
        for strategy in filters["selected_strategies"]:
            strategy_log_path = f"logs/strategies/{strategy}.log"
            if os.path.exists(strategy_log_path):
                logs = load_logs(strategy_log_path)
                for log in logs:
                    log["strategy"] = strategy
                strategy_logs.extend(logs)
        
        if strategy_logs:
            # Create DataFrame
            logs_df = pd.DataFrame(strategy_logs)
            
            # Format columns
            logs_df["timestamp"] = logs_df["timestamp"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Apply date filter
            logs_df["date"] = pd.to_datetime(logs_df["timestamp"]).dt.date
            filtered_logs = logs_df[
                (logs_df["date"] >= filters["start_date"]) &
                (logs_df["date"] <= filters["end_date"])
            ]
            
            if not filtered_logs.empty:
                st.dataframe(filtered_logs[["timestamp", "strategy", "level", "message"]], use_container_width=True)
            else:
                st.info("No strategy logs found for the selected date range")
        else:
            st.info("No strategy logs available")
    
    # Error logs
    with log_tabs[2]:
        error_logs = []
        
        # Load main error logs
        main_logs = load_logs("logs/main.log")
        for log in main_logs:
            if log["level"] == "ERROR":
                error_logs.append(log)
        
        # Load strategy error logs
        for strategy in filters["selected_strategies"]:
            strategy_log_path = f"logs/strategies/{strategy}.log"
            if os.path.exists(strategy_log_path):
                logs = load_logs(strategy_log_path)
                for log in logs:
                    if log["level"] == "ERROR":
                        log["strategy"] = strategy
                        error_logs.append(log)
        
        if error_logs:
            # Create DataFrame
            logs_df = pd.DataFrame(error_logs)
            
            # Format columns
            logs_df["timestamp"] = logs_df["timestamp"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Apply date filter
            logs_df["date"] = pd.to_datetime(logs_df["timestamp"]).dt.date
            filtered_logs = logs_df[
                (logs_df["date"] >= filters["start_date"]) &
                (logs_df["date"] <= filters["end_date"])
            ]
            
            if not filtered_logs.empty:
                if "strategy" in filtered_logs.columns:
                    st.dataframe(filtered_logs[["timestamp", "strategy", "message"]], use_container_width=True)
                else:
                    st.dataframe(filtered_logs[["timestamp", "message"]], use_container_width=True)
            else:
                st.info("No error logs found for the selected date range")
        else:
            st.info("No error logs available")

def main():
    """Main dashboard function."""
    # Render sidebar with filters
    filters = render_sidebar()
    
    # Dashboard header
    st.title("Trading Bot Dashboard")
    
    # Render overview section
    render_overview(filters)
    
    # Render performance charts
    render_performance_charts(filters)
    
    # Render open positions
    render_open_positions(filters)
    
    # Render log viewer
    render_log_viewer(filters)
    
    # Auto-refresh the dashboard
    if st.button("Refresh Now"):
        st.experimental_rerun()
    
    # Display last refresh time
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Set up auto-refresh
    if filters["refresh_interval"] > 0:
        time.sleep(filters["refresh_interval"])
        st.experimental_rerun()

if __name__ == "__main__":
    main() 