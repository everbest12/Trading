import os
import json
from typing import Dict, Any, List, Optional
import openai
from datetime import datetime
import re

class StrategyGenerator:
    """
    Uses LLM to generate trading strategies from natural language prompts.
    """
    
    def __init__(self, config_path: str):
        """Initialize the strategy generator with configuration."""
        self.config = self._load_config(config_path)
        self._setup_api()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        with open(config_path, 'r') as file:
            return json.load(file)
    
    def _setup_api(self) -> None:
        """Set up the OpenAI API client."""
        openai.api_key = self.config.get('openai', {}).get('api_key', os.getenv('OPENAI_API_KEY'))
        if not openai.api_key:
            raise ValueError("OpenAI API key not found in config or environment variables")
    
    def generate_strategy(self, prompt: str) -> Dict[str, Any]:
        """
        Generate a trading strategy from a natural language prompt.
        
        Args:
            prompt: A description of the trading strategy, e.g., "trade gold based on MACD"
            
        Returns:
            A dictionary containing the generated strategy components
        """
        # Enhance the prompt with strategy requirements
        enhanced_prompt = self._enhance_prompt(prompt)
        
        # Call the OpenAI API
        response = openai.ChatCompletion.create(
            model=self.config.get('openai', {}).get('model', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are an expert forex trading strategy developer. Your task is to translate natural language descriptions into detailed, executable trading strategies."},
                {"role": "user", "content": enhanced_prompt}
            ],
            temperature=self.config.get('openai', {}).get('temperature', 0.2),
            max_tokens=self.config.get('openai', {}).get('max_tokens', 2000)
        )
        
        # Extract and parse the response
        strategy_text = response.choices[0].message.content
        
        # Parse the strategy text into components
        strategy = self._parse_strategy(strategy_text)
        
        # Save the generated strategy
        self._save_strategy(prompt, strategy)
        
        return strategy
    
    def _enhance_prompt(self, prompt: str) -> str:
        """Enhance the user prompt with additional instructions."""
        template = """
        Based on the following description: "{prompt}"
        
        Generate a complete trading strategy with the following components:
        
        1. Strategy Name: A descriptive name for the strategy
        2. Description: A brief overview of how the strategy works
        3. Market: The market(s) this strategy is designed for (e.g., Forex, Gold, Crypto)
        4. Timeframe: Recommended timeframe(s) for this strategy
        5. Indicators: Technical indicators used with their parameters
        6. Entry Conditions: Precise conditions for entering a trade
        7. Exit Conditions: Conditions for exiting a trade (take profit and stop loss)
        8. Risk Management: Position sizing and risk per trade
        9. Python Code: Executable Python code that implements the strategy
        
        Format the response as a structured document with these sections.
        Ensure the Python code is complete, including all necessary imports and functions.
        The code should be compatible with our platform which uses MetaTrader 5 for execution.
        """
        
        return template.format(prompt=prompt)
    
    def _parse_strategy(self, strategy_text: str) -> Dict[str, Any]:
        """Parse the generated strategy text into components."""
        strategy = {
            "raw_text": strategy_text,
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Extract components based on headers
        sections = [
            "Strategy Name", "Description", "Market", "Timeframe", 
            "Indicators", "Entry Conditions", "Exit Conditions", 
            "Risk Management", "Python Code"
        ]
        
        current_section = None
        current_content = []
        
        for line in strategy_text.split('\n'):
            # Check if line contains a section header
            matched_section = None
            for section in sections:
                if section in line and (line.startswith(section) or line.strip().startswith(section)):
                    matched_section = section
                    break
            
            if matched_section:
                # Save the previous section if it exists
                if current_section and current_content:
                    strategy["components"][current_section] = '\n'.join(current_content).strip()
                    current_content = []
                
                current_section = matched_section
            elif current_section:
                current_content.append(line)
        
        # Save the last section
        if current_section and current_content:
            strategy["components"][current_section] = '\n'.join(current_content).strip()
        
        # Extract Python code
        if "Python Code" in strategy["components"]:
            code = strategy["components"]["Python Code"]
            # Clean up code block markers if present
            code = self._clean_code_block(code)
            strategy["components"]["Python Code"] = code
        
        return strategy
    
    def _clean_code_block(self, code: str) -> str:
        """Clean up code block markers from the code."""
        # Remove markdown code block markers
        if re.search(r'```python', code):
            code = re.sub(r'```python', '', code)
        if re.search(r'```', code):
            code = re.sub(r'```', '', code)
        
        return code.strip()
    
    def _save_strategy(self, prompt: str, strategy: Dict[str, Any]) -> None:
        """Save the generated strategy to a file."""
        # Create a safe filename from the prompt
        safe_name = ''.join(c if c.isalnum() else '_' for c in prompt)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"src/strategies/generated/{timestamp}_{safe_name}.json"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Save the strategy
        with open(filename, 'w') as file:
            json.dump(strategy, file, indent=2)
    
    def scaffold_strategy_file(self, strategy: Dict[str, Any]) -> str:
        """
        Create a Python file from the generated strategy.
        
        Args:
            strategy: The generated strategy dictionary
            
        Returns:
            Path to the created Python file
        """
        # Extract strategy name and create a safe filename
        strategy_name = strategy.get('components', {}).get('Strategy Name', 'untitled_strategy')
        safe_name = ''.join(c if c.isalnum() else '_' for c in strategy_name).lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"src/strategies/generated/{timestamp}_{safe_name}.py"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Extract the Python code
        python_code = strategy.get('components', {}).get('Python Code', '')
        
        # Add header with metadata
        header = f"""# Strategy: {strategy.get('components', {}).get('Strategy Name', 'Untitled Strategy')}
# Generated at: {strategy.get('timestamp', datetime.now().isoformat())}
# Description: {strategy.get('components', {}).get('Description', 'No description')}
# Market: {strategy.get('components', {}).get('Market', 'Unknown')}
# Timeframe: {strategy.get('components', {}).get('Timeframe', 'Unknown')}

"""
        
        # Write the file
        with open(filename, 'w') as file:
            file.write(header + python_code)
        
        return filename

if __name__ == "__main__":
    # Example usage
    config_path = "config/api_keys.json"
    generator = StrategyGenerator(config_path)
    
    prompt = "Create a strategy that trades gold based on MACD crossovers and RSI confirmation"
    strategy = generator.generate_strategy(prompt)
    
    # Print generated strategy components
    for section, content in strategy.get('components', {}).items():
        if section != "Python Code":
            print(f"{section}:\n{content}\n")
        else:
            print(f"{section}: [code snippet not displayed due to length]")
    
    # Scaffold the strategy into a Python file
    python_file = generator.scaffold_strategy_file(strategy)
    print(f"\nStrategy saved to: {python_file}") 