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
    CREATED = "created"    # Room created, not yet started
    WAITING = "waiting"    # Waiting for opponent (invites/queue)
    ACTIVE = "active"      # Game in progress
    FINISHED = "finished"  # Game finished
    ABORTED = "aborted"    # Game aborted/terminated


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
    board_size: int  # Raw size code (e.g. 3, 4, 10304)
    player_a_id: int  # Telegram ID
    
    # Board dimensions (derived from board_size)
    board_width: int = 3
    board_height: int = 3
    
    # Input mode: "classic" (grid) or "numbered" (keypad)
    input_mode: str = "classic"
    
    # Players
    player_b_id: Optional[int] = None  # None for pending PvP or PvE bot
    
    # PvE specific
    bot_difficulty: Optional[str] = None  # "easy", "medium", "hard"
    
    # Game state
    board: Optional[Board] = None
    current_player_index: int = 0  # 0 = player_a, 1 = player_b
    state: RoomState = RoomState.CREATED
    state_version: int = 0
    move_number: int = 0
    end_reason: Optional[str] = None
    end_reason_detail: Optional[str] = None
    
    # Player customization (cached at game start)
    player_a_emoji: str = "😀"
    player_b_emoji: str = "😎"
    theme: str = "classic"
    
    # UI State
    current_page: int = 0  # For paginated keyboards (lines mode)
    
    # Turn tracking
    consecutive_timeouts_a: int = 0
    consecutive_timeouts_b: int = 0
    turn_started_at: Optional[datetime] = None
    turn_version: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    last_activity_at: datetime = field(default_factory=datetime.now)
    
    # Invite code for friend matches
    invite_code: Optional[str] = None
    
    # Message IDs for editing (instead of sending new messages)
    message_a_id: Optional[int] = None  # Player A's game message ID
    message_b_id: Optional[int] = None  # Player B's game message ID
    
    def __post_init__(self):
        # Calculate dimensions and mode if not set properly (e.g. init from raw size)
        # Note: create_room handles this explicitly, but good for safety
        if self.board is None and self.state not in {RoomState.CREATED, RoomState.WAITING}:
            self.board = create_board(self.board_size, width=self.board_width, height=self.board_height)
    
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
        self.turn_version = self.state_version
    
    def keep_current_player(self) -> None:
        """Keep current player for extra turn."""
        self.turn_started_at = datetime.now()
        self.turn_version = self.state_version
    
    def start_game(self) -> None:
        """Initialize and start the game."""
        self.board = create_board(self.board_size, width=self.board_width, height=self.board_height)
        self.state = RoomState.ACTIVE
        self.turn_started_at = datetime.now()
        self.turn_version = self.state_version
    
    def complete_game(self) -> None:
        """Mark game as completed."""
        self.state = RoomState.FINISHED
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
    
    def set_message_id(self, telegram_id: int, message_id: int) -> None:
        """Store message ID for a player."""
        if telegram_id == self.player_a_id:
            self.message_a_id = message_id
        else:
            self.message_b_id = message_id
    
    def get_message_id(self, telegram_id: int) -> Optional[int]:
        """Get stored message ID for a player."""
        if telegram_id == self.player_a_id:
            return self.message_a_id
        return self.message_b_id


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
    
    # Decode board size and mode
    if board_size > 100:
        # Encoded: 10304 -> 3x4
        w = int((board_size - 10000) / 100)
        h = board_size % 100
        width = w
        height = h
    else:
        width = board_size
        height = board_size
        
    # Determine input mode
    # Telegram inline keyboard limit is 8 columns.
    # Grid columns = 2 * width + 1.
    grid_cols = 2 * width + 1
    
    # Specific override for 5x5 and 6x6 (lines mode)
    if width in [5, 6] and height in [5, 6]:
        input_mode = "lines"
    # 4x4 allows classic mode (try to fit)
    elif width == 4 and height == 4:
        input_mode = "classic"
    elif grid_cols > 9: # Allow 9 columns for 4x4 classic (may require testing)
        input_mode = "numbered"
    else:
        input_mode = "classic"
    
    initial_state = RoomState.CREATED
    if mode == GameMode.PVP_FRIEND and player_b_id is None:
        initial_state = RoomState.WAITING

    room = Room(
        id=room_id,
        mode=mode,
        board_size=board_size,
        board_width=width,
        board_height=height,
        input_mode=input_mode,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        bot_difficulty=bot_difficulty,
        player_a_emoji=player_a_emoji,
        player_b_emoji=player_b_emoji,
        theme=theme,
        state=initial_state,
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
