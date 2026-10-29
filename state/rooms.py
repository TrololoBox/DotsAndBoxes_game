"""
Room management for game sessions.

Handles room lifecycle: creation, state transitions, and cleanup.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict
import uuid
import asyncio

from game.turn import apply_turn, TurnResult

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
    state: RoomState = RoomState.PENDING
    state_version: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)
    last_timeout_version: Optional[int] = None
    
    # Player customization (cached at game start)
    player_a_emoji: str = "😀"
    player_b_emoji: str = "😎"
    theme: str = "classic"
    
    # UI State
    current_page: int = 0  # For paginated keyboards (lines mode)
    pages_by_player: Dict[int, int] = field(default_factory=dict)

    # Presentation history is committed with the move, never during delivery.
    last_move_edge_id: Optional[str] = None
    last_move_player_id: Optional[str] = None
    recent_edge_ids: list[str] = field(default_factory=list)
    recent_captures: int = 0
    last_turns: Dict[str, list[str]] = field(default_factory=dict)
    
    # Turn tracking
    consecutive_timeouts_a: int = 0
    consecutive_timeouts_b: int = 0
    turn_started_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Invite code for friend matches
    invite_code: Optional[str] = None
    
    # Message IDs for editing (instead of sending new messages)
    message_a_id: Optional[int] = None  # Player A's game message ID
    message_b_id: Optional[int] = None  # Player B's game message ID
    
    # Rematch tracking
    rematch_requester_id: Optional[int] = None  # Who requested rematch
    
    def __post_init__(self):
        # Calculate dimensions and mode if not set properly (e.g. init from raw size)
        # Note: create_room handles this explicitly, but good for safety
        if self.board is None and self.state != RoomState.PENDING:
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
        self.state_version += 1
    
    def keep_current_player(self) -> None:
        """Keep current player for extra turn."""
        self.turn_started_at = datetime.now()
        self.state_version += 1
    
    def start_game(self) -> None:
        """Initialize and start the game."""
        if self.state != RoomState.PENDING:
            raise ValueError("Only a pending room can start")
        self.board = create_board(self.board_size, width=self.board_width, height=self.board_height)
        self.state = RoomState.ACTIVE
        self.turn_started_at = datetime.now()
        self.state_version += 1
    
    def complete_game(self) -> None:
        """Mark game as completed."""
        if self.state != RoomState.ACTIVE:
            return
        self.state = RoomState.COMPLETED
        self.completed_at = datetime.now()
        self.state_version += 1
    
    def apply_move(self, player_id: str, edge_id: str) -> Optional[TurnResult]:
        """Commit one full move synchronously, before Telegram I/O can yield."""
        if self.state != RoomState.ACTIVE or self.board is None:
            return None
        current = "bot" if self.is_pve() and self.current_player_index == 1 else str(self.current_player_id)
        other = "bot" if self.is_pve() and self.current_player_index == 0 else str(self.other_player_id)
        if player_id != current:
            return None
        result = apply_turn(self.board, player_id, edge_id, current, other)
        if not result.success:
            return result
        if self.last_move_player_id != player_id:
            self.recent_edge_ids = []
            self.recent_captures = 0
        self.recent_edge_ids.append(edge_id)
        self.recent_captures += len(result.captures)
        self.last_turns[player_id] = list(self.recent_edge_ids)
        self.last_move_edge_id = edge_id
        self.last_move_player_id = player_id
        if self.current_player_index == 0:
            self.consecutive_timeouts_a = 0
        else:
            self.consecutive_timeouts_b = 0
        if result.game_over:
            self.complete_game()
        elif result.extra_turn:
            self.keep_current_player()
        else:
            self.switch_player()
        return result

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
        
    # All sizes use the same stable number on the picture and on the keypad.
    input_mode = "numbered"
    
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
        from state.players import get_player, set_player_room
        for uid in (room.player_a_id, room.player_b_id):
            player = get_player(uid) if uid is not None else None
            if player and player.current_room_id == room_id:
                set_player_room(uid, None)
        room.state = RoomState.ABANDONED
        room.state_version += 1
        del _rooms[room_id]


def get_all_rooms() -> list[Room]:
    """Get all active rooms."""
    return list(_rooms.values())


def clear_all_rooms() -> None:
    """Clear all rooms (for restart)."""
    _rooms.clear()
    _invite_codes.clear()
