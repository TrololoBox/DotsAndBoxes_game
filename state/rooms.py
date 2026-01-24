"""
Room management for game sessions.

Handles room lifecycle: creation, state transitions, and cleanup.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict
import uuid

from game.board import Board, create_board


class RoomState(Enum):
    """Room lifecycle states."""
    PENDING = "pending"      # Waiting for opponent (invites)
    ACTIVE = "active"        # Game in progress
    COMPLETED = "completed"  # Game finished
    ABANDONED = "abandoned"  # Cleaned up


class GameMode(Enum):
    """Game mode types."""
    PVE = "pve"
    PVP_WORLD = "pvp_world"
    PVP_FRIEND = "pvp_friend"


@dataclass
class Room:
    """Game room containing match state."""
    id: str
    mode: GameMode
    board_size: int
    
    # Players
    player_a_id: int  # Telegram ID
    player_b_id: Optional[int] = None  # None for pending PvP or PvE bot
    
    # PvE specific
    bot_difficulty: Optional[str] = None  # "easy", "medium", "hard"
    
    # Game state
    board: Optional[Board] = None
    current_player_index: int = 0  # 0 = player_a, 1 = player_b
    state: RoomState = RoomState.PENDING
    
    # Player customization (cached at game start)
    player_a_emoji: str = "😀"
    player_b_emoji: str = "😎"
    theme: str = "classic"
    
    # Turn tracking
    consecutive_timeouts_a: int = 0
    consecutive_timeouts_b: int = 0
    turn_started_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Invite code for friend matches
    invite_code: Optional[str] = None
    
    def __post_init__(self):
        if self.board is None and self.state != RoomState.PENDING:
            self.board = create_board(self.board_size)
    
    @property
    def current_player_id(self) -> Optional[int]:
        """Get Telegram ID of current player."""
        if self.current_player_index == 0:
            return self.player_a_id
        return self.player_b_id
    
    @property
    def other_player_id(self) -> Optional[int]:
        """Get Telegram ID of non-current player."""
        if self.current_player_index == 0:
            return self.player_b_id
        return self.player_a_id
    
    def switch_player(self) -> None:
        """Switch to the other player's turn."""
        self.current_player_index = 1 - self.current_player_index
        self.turn_started_at = datetime.now()
    
    def keep_current_player(self) -> None:
        """Keep current player for extra turn."""
        self.turn_started_at = datetime.now()
    
    def start_game(self) -> None:
        """Initialize and start the game."""
        self.board = create_board(self.board_size)
        self.state = RoomState.ACTIVE
        self.turn_started_at = datetime.now()
    
    def complete_game(self) -> None:
        """Mark game as completed."""
        self.state = RoomState.COMPLETED
        self.completed_at = datetime.now()
    
    def is_pve(self) -> bool:
        """Check if this is a PvE game."""
        return self.mode == GameMode.PVE
    
    def is_player_turn(self, telegram_id: int) -> bool:
        """Check if it's a specific player's turn."""
        return self.current_player_id == telegram_id
    
    def get_player_emoji(self, telegram_id: int) -> str:
        """Get emoji for a player."""
        if telegram_id == self.player_a_id:
            return self.player_a_emoji
        return self.player_b_emoji


# In-memory room storage
_rooms: Dict[str, Room] = {}
_invite_codes: Dict[str, str] = {}  # invite_code -> room_id


def create_room(
    mode: GameMode,
    board_size: int,
    player_a_id: int,
    player_b_id: Optional[int] = None,
    bot_difficulty: Optional[str] = None,
    player_a_emoji: str = "😀",
    player_b_emoji: str = "😎",
    theme: str = "classic",
) -> Room:
    """Create a new game room."""
    room_id = str(uuid.uuid4())[:8]
    
    room = Room(
        id=room_id,
        mode=mode,
        board_size=board_size,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        bot_difficulty=bot_difficulty,
        player_a_emoji=player_a_emoji,
        player_b_emoji=player_b_emoji,
        theme=theme,
    )
    
    # For friend invites, generate invite code
    if mode == GameMode.PVP_FRIEND:
        invite_code = str(uuid.uuid4())[:6].upper()
        room.invite_code = invite_code
        _invite_codes[invite_code] = room_id
    
    _rooms[room_id] = room
    return room


def get_room(room_id: str) -> Optional[Room]:
    """Get room by ID."""
    return _rooms.get(room_id)


def get_room_by_invite(invite_code: str) -> Optional[Room]:
    """Get room by invite code."""
    room_id = _invite_codes.get(invite_code.upper())
    if room_id:
        return _rooms.get(room_id)
    return None


def delete_room(room_id: str) -> None:
    """Remove a room from storage."""
    room = _rooms.get(room_id)
    if room:
        if room.invite_code and room.invite_code in _invite_codes:
            del _invite_codes[room.invite_code]
        del _rooms[room_id]


def get_all_rooms() -> list[Room]:
    """Get all active rooms."""
    return list(_rooms.values())


def clear_all_rooms() -> None:
    """Clear all rooms (for restart)."""
    _rooms.clear()
    _invite_codes.clear()
