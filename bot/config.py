"""
DotsAndBoxes Telegram Bot Configuration

Loads settings from environment variables.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


# Bot token from BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.DEBUG)
)

logger = logging.getLogger(__name__)


# Game settings
class GameConfig:
    """Game-related configuration constants."""
    
    # Supported board sizes (in squares)
    BOARD_SIZES = [3, 4, 5]
    
    # Turn timers (seconds)
    PVE_TURN_TIME = 60
    PVP_TURN_TIME = 45
    
    # AFK threshold (consecutive timeouts before showing AFK choice)
    AFK_TIMEOUT_THRESHOLD = 2
    
    # Max concurrent games per user
    MAX_GAMES_PER_USER = 1


# Rendering themes
THEMES = {
    "classic": {
        "name": "Классика",
        "player_a": "#2F80ED",
        "player_b": "#EB5757",
        "neutral": "#BDBDBD",
        "background": "#F2F2F2",
    },
    "forest": {
        "name": "Лес",
        "player_a": "#219653",
        "player_b": "#F2994A",
        "neutral": "#BDBDBD",
        "background": "#F2F2F2",
    },
    "night": {
        "name": "Ночь",
        "player_a": "#56CCF2",
        "player_b": "#BB6BD9",
        "neutral": "#4F4F4F",
        "background": "#1B1B1B",
    },
}

DEFAULT_THEME = "classic"
DEFAULT_EMOJI = "😀"
FALLBACK_EMOJI = "👤"  # Used when both players pick the same emoji
