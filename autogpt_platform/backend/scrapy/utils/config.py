"""
Configuration management for the scraper system.
Loads settings from environment variables and provides defaults.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("scrapy.config")

# Basic configuration
CONFIG = {
    # Directories
    "STRATEGIES_DIR": os.path.join(os.path.dirname(os.path.dirname(__file__)), "strategies"),
    "RESULTS_DIR": os.path.join(os.path.dirname(os.path.dirname(__file__)), "results"),
    "SNAPSHOT_DIR": os.path.join(os.path.dirname(os.path.dirname(__file__)), "snapshots"),

    # Scraping settings
    "REQUEST_TIMEOUT": 30,
    "RETRY_COUNT": 3,
    "FORCE_REFRESH": False,
    "DEBUG_MODE": os.getenv("DEBUG_MODE", "false").lower() == "true",
    
    # AI settings
    "AI_ENABLED": True,
    "AI_MODEL": os.getenv("AI_MODEL", "gpt-4o-mini"),

    # Azure OpenAI settings
    "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY1", ""),
    "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    "AZURE_OPENAI_4OM_ENDPOINT": os.getenv("AZURE_OPENAI_4OM_ENDPOINT", ""),
    "AZURE_OPENAI_O1_ENDPOINT": os.getenv("AZURE_OPENAI_O1_ENDPOINT", ""),
    "AZURE_OPENAI_O3_ENDPOINT": os.getenv("AZURE_OPENAI_O3_ENDPOINT", ""),

    # HTTP headers
    "DEFAULT_HEADERS": {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
}


# Create directories if they don't exist
for directory in [CONFIG["SNAPSHOT_DIR"], CONFIG["RESULTS_DIR"], CONFIG["STRATEGIES_DIR"]]:
    os.makedirs(directory, exist_ok=True)

# URL patterns for common websites
URL_PATTERNS = {
    "lbbonline.com": {
        "project": r"https?://(?:www\.)?lbbonline\.com/work/\d+.*",
        "company": r"https?://(?:www\.)?lbbonline\.com/companies/.*",
        "person": r"https?://(?:www\.)?lbbonline\.com/people/.*",
        "listing": r"https?://(?:www\.)?lbbonline\.com/work\?.*",
    },
    "dandad.org": {
        "project": r"https?://(?:www\.)?dandad\.org/awards/.*/\d+/.*",
        "company": r"https?://(?:www\.)?dandad\.org/profiles/.*",
        "listing": r"https?://(?:www\.)?dandad\.org/search/archive/.*",
    },
    "eyecannndy.com": {
        "project": r"https?://(?:www\.)?eyecannndy\.com/project/.*",
        "listing": r"https?://(?:www\.)?eyecannndy\.com/technique/.*",
    }
}

# Create subdirectories for common domains
common_domains = ["lbbonline", "dandad", "eyecannndy"]
for domain in common_domains:
    os.makedirs(os.path.join(CONFIG["RESULTS_DIR"], domain), exist_ok=True)
    os.makedirs(os.path.join(CONFIG["STRATEGIES_DIR"], domain), exist_ok=True)

# Function to get the next version number for a strategy or result
def get_next_version(domain, base_dir, prefix="v"):
    """Get the next sequential version number for a domain"""
    domain_dir = os.path.join(base_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)
    
    existing_files = os.listdir(domain_dir)
    version_numbers = []
    
    for filename in existing_files:
        if filename.startswith(prefix):
            try:
                version_str = filename.split("_")[0][len(prefix):]
                version_numbers.append(int(version_str))
            except (ValueError, IndexError):
                pass
    
    if not version_numbers:
        return f"{prefix}001"
    
    next_version = max(version_numbers) + 1
    return f"{prefix}{next_version:03d}"



def load_custom_config(config_path: str) -> Dict[str, Any]:
    """Load custom configuration from a JSON file"""
    try:
        with open(config_path, "r") as f:
            custom_config = json.load(f)
        
        # Merge with default config
        for key, value in custom_config.items():
            if isinstance(value, dict) and key in CONFIG and isinstance(CONFIG[key], dict):
                # For nested dictionaries, merge them
                CONFIG[key].update(value)
            else:
                # For scalar values, replace them
                CONFIG[key] = value
        
        return CONFIG
    except Exception as e:
        logger.error(f"Failed to load custom config from {config_path}: {e}")
        return CONFIG

# Check if Azure OpenAI is properly configured
def is_azure_openai_configured() -> bool:
    """Check if Azure OpenAI is properly configured"""
    return bool(CONFIG["AZURE_OPENAI_API_KEY"] and 
               (CONFIG["AZURE_OPENAI_ENDPOINT"] or 
                CONFIG["AZURE_OPENAI_4OM_ENDPOINT"] or
                CONFIG["AZURE_OPENAI_O1_ENDPOINT"] or
                CONFIG["AZURE_OPENAI_O3_ENDPOINT"]))

def get_openai_endpoint(model: str) -> str:
    """Get the appropriate endpoint for the specified model"""
    if model == "gpt-4o":
        return CONFIG["AZURE_OPENAI_ENDPOINT"]
    elif model == "gpt-4o-mini":
        return CONFIG["AZURE_OPENAI_4OM_ENDPOINT"]
    elif model == "o1-mini":
        return CONFIG["AZURE_OPENAI_O1_ENDPOINT"]
    elif model == "o3-mini":
        return CONFIG["AZURE_OPENAI_O3_ENDPOINT"]
    else:
        # Default to GPT-4o Mini
        return CONFIG["AZURE_OPENAI_4OM_ENDPOINT"]

if __name__ == "__main__":
    # Test configuration
    print("Configuration loaded:")
    
    for key, value in CONFIG.items():
        if key != "DEFAULT_HEADERS" and not key.startswith("AZURE_"):
            print(f"  {key}: {value}")
    
    # Check if AI is configured
    if is_azure_openai_configured():
        print("✅ Azure OpenAI is configured")
        print(f"  Model: {CONFIG['AI_MODEL']}")
        print(f"  Endpoint: {get_openai_endpoint(CONFIG['AI_MODEL'])}")
    else:
        print("⚠️ Azure OpenAI is not properly configured")