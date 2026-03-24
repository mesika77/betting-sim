"""Shared configuration helpers for the betting-sim bot."""
import os
from dotenv import load_dotenv

load_dotenv()

def get_api_key() -> str:
    """Get The Odds API key from environment."""
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise ValueError("ODDS_API_KEY environment variable is not set")
    return key
