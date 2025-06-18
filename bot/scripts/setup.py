#!/usr/bin/env python3
"""
Setup script for the LLM-augmented forex trading platform.
This script initializes the project directory structure and configuration files.
"""

import os
import sys
import json
import shutil
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_directory(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")
    else:
        print(f"Directory already exists: {path}")

def create_file(path, content=""):
    """Create file with given content if it doesn't exist."""
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(content)
        print(f"Created file: {path}")
    else:
        print(f"File already exists: {path}")

def copy_example_config():
    """Copy example config files to actual config files if they don't exist."""
    source = "config/api_keys.json.example"
    target = "config/api_keys.json"
    
    if os.path.exists(source) and not os.path.exists(target):
        shutil.copy(source, target)
        print(f"Copied {source} to {target}")
    else:
        print(f"Skipped copying {source} (target already exists or source not found)")

def create_init_files():
    """Create __init__.py files in all Python package directories."""
    for root, dirs, files in os.walk("src"):
        if root.endswith("__pycache__"):
            continue
            
        init_path = os.path.join(root, "__init__.py")
        create_file(init_path)

def create_mt5_config():
    """Create MT5 configuration file if it doesn't exist."""
    config_path = "config/brokers/mt5_config.json"
    
    if not os.path.exists(config_path):
        config = {
            "login": 0,
            "password": "your_password",
            "server": "your_broker_server",
            "terminal_path": "C:/Program Files/MetaTrader 5/terminal64.exe"  # Default path for Windows
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
            
        print(f"Created MT5 config: {config_path}")
    else:
        print(f"MT5 config already exists: {config_path}")

def create_readme_files():
    """Create README.md files in key directories."""
    readme_files = {
        "src/brokers/README.md": "# Broker Connectors\n\nThis directory contains connector modules for various brokers and exchanges.\n",
        "src/indicators/README.md": "# Technical Indicators\n\nThis directory contains implementations of various technical indicators.\n",
        "src/strategies/README.md": "# Trading Strategies\n\nThis directory contains trading strategy implementations.\n",
        "src/llm/README.md": "# LLM Integration\n\nThis directory contains modules for integrating Large Language Models into the trading platform.\n",
        "src/backtesting/README.md": "# Backtesting Engine\n\nThis directory contains the backtesting engine and related utilities.\n",
        "notebooks/README.md": "# Jupyter Notebooks\n\nThis directory contains Jupyter notebooks for strategy development, market analysis, and backtesting.\n",
    }
    
    for path, content in readme_files.items():
        create_file(path, content)

def main():
    """Main setup function."""
    print("Setting up LLM-augmented forex trading platform...")
    
    # Create directory structure
    required_dirs = [
        "config/brokers",
        "data/historical",
        "data/news",
        "data/market_analysis",
        "src/brokers",
        "src/indicators/momentum",
        "src/indicators/volatility",
        "src/indicators/trend",
        "src/indicators/custom",
        "src/strategies/session_based",
        "src/strategies/event_driven",
        "src/strategies/technical",
        "src/strategies/templates",
        "src/strategies/generated",
        "src/risk_management",
        "src/llm/prompts",
        "src/backtesting",
        "src/utils",
        "logs/trades",
        "logs/errors",
        "logs/performance",
        "notebooks/strategy_development",
        "notebooks/market_analysis",
        "notebooks/backtesting",
        "docs/api",
        "docs/guides",
        "docs/examples",
        "tests/unit",
        "tests/integration",
        "tests/fixtures",
        "scripts/data_downloaders",
        "scripts/maintenance",
        "ui/dashboard",
        "ui/reports",
        "ui/bot_controls"
    ]
    
    for directory in required_dirs:
        create_directory(directory)
    
    # Create __init__.py files
    create_init_files()
    
    # Create README files
    create_readme_files()
    
    # Copy example config
    copy_example_config()
    
    # Create MT5 config
    create_mt5_config()
    
    # Create .gitignore if it doesn't exist
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
config/api_keys.json
logs/
data/historical/
data/market_analysis/
.env
"""
    create_file(".gitignore", gitignore_content)
    
    print("\nSetup completed successfully!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Configure your API keys in config/api_keys.json")
    print("3. Configure your MT5 connection in config/brokers/mt5_config.json")
    print("4. Run a test strategy or start development")

if __name__ == "__main__":
    main() 