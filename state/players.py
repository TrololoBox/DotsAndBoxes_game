"""
Player profile management.

Stores player preferences and tracks active sessions.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime


@dataclass
class PlayerProfile:
    """Player profile with preferences and session state."""
    telegram_id: int
    username: str
    first_name: str
    
    # Customization
    emoji: str = "😀"
    theme: str = "classic"
    
    # Active session
    current_room_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_active = datetime.now()
    
    @property
    def is_in_game(self) -> bool:
        """Check if player is currently in a game."""
        return self.current_room_id is not None
    
    @property
    def display_name(self) -> str:
        """Get display name for the player."""
        return f"@{self.username}" if self.username else self.first_name


# In-memory player storage
_players: Dict[int, PlayerProfile] = {}


def get_player(telegram_id: int) -> Optional[PlayerProfile]:
    """Get player by Telegram ID."""
    return _players.get(telegram_id)


def get_or_create_player(
    telegram_id: int,
    username: str,
    first_name: str,
) -> PlayerProfile:
    """Get existing player or create new one."""
    if telegram_id in _players:
        player = _players[telegram_id]
        player.update_activity()
        return player
    
    player = PlayerProfile(
        telegram_id=telegram_id,
        username=username or "",
        first_name=first_name,
    )
    _players[telegram_id] = player
    return player


def update_player_emoji(telegram_id: int, emoji: str) -> bool:
    """Update player's chosen emoji."""
    player = _players.get(telegram_id)
    if player:
        player.emoji = emoji
        return True
    return False


def update_player_theme(telegram_id: int, theme: str) -> bool:
    """Update player's chosen theme."""
    player = _players.get(telegram_id)
    if player:
        player.theme = theme
        return True
    return False


def set_player_room(telegram_id: int, room_id: Optional[str]) -> None:
    """Set player's current room."""
    player = _players.get(telegram_id)
    if player:
        player.current_room_id = room_id


def clear_all_players() -> None:
    """Clear all player data (for restart)."""
    _players.clear()
