"""
Turn timer and AFK handling.

Manages turn timeouts and triggers AFK flow.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

from state.rooms import Room, GameMode


logger = logging.getLogger(__name__)


# Timer settings (from config)
PVE_TURN_TIME = 60  # seconds
PVP_TURN_TIME = 45  # seconds
AFK_THRESHOLD = 2   # consecutive timeouts before AFK choice


class AFKChoice(Enum):
    """Options presented to AFK player."""
    CONTINUE_WITH_BOT = "continue_bot"
    SURRENDER = "surrender"


@dataclass
class TimerStatus:
    """Status of current turn timer."""
    seconds_remaining: int
    is_expired: bool
    consecutive_timeouts: int
    should_show_afk_choice: bool


def get_turn_duration(room: Room) -> int:
    """Get turn duration in seconds based on game mode."""
    if room.mode == GameMode.PVE:
        return PVE_TURN_TIME
    return PVP_TURN_TIME


def get_timer_status(room: Room) -> TimerStatus:
    """
    Check the current turn timer status.
    
    Returns:
        TimerStatus with remaining time and AFK info
    """
    if room.turn_started_at is None:
        return TimerStatus(
            seconds_remaining=get_turn_duration(room),
            is_expired=False,
            consecutive_timeouts=0,
            should_show_afk_choice=False,
        )
    
    elapsed = datetime.now() - room.turn_started_at
    duration = get_turn_duration(room)
    remaining = max(0, duration - int(elapsed.total_seconds()))
    is_expired = remaining <= 0
    
    # Get consecutive timeouts for current player
    if room.current_player_index == 0:
        timeouts = room.consecutive_timeouts_a
    else:
        timeouts = room.consecutive_timeouts_b
    
    return TimerStatus(
        seconds_remaining=remaining,
        is_expired=is_expired,
        consecutive_timeouts=timeouts,
        should_show_afk_choice=timeouts >= AFK_THRESHOLD,
    )


def handle_timeout(room: Room) -> bool:
    """
    Handle a turn timeout.
    
    Updates consecutive timeout counter and determines if AFK flow is needed.
    
    Returns:
        True if should show AFK choice, False otherwise
    """
    # Increment timeout counter for current player
    if room.current_player_index == 0:
        room.consecutive_timeouts_a += 1
        timeouts = room.consecutive_timeouts_a
    else:
        room.consecutive_timeouts_b += 1
        timeouts = room.consecutive_timeouts_b
    
    logger.info(
        f"Room {room.id}: Player {room.current_player_id} timed out "
        f"({timeouts} consecutive)"
    )
    
    return timeouts >= AFK_THRESHOLD


def reset_timeout_counter(room: Room) -> None:
    """Reset timeout counter for current player (they made a move)."""
    if room.current_player_index == 0:
        room.consecutive_timeouts_a = 0
    else:
        room.consecutive_timeouts_b = 0


def format_time_remaining(seconds: int) -> str:
    """Format remaining time for display."""
    if seconds <= 0:
        return "0:00"
    
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def get_timeout_message(room: Room, is_your_turn: bool) -> str:
    """Get friendly timeout message."""
    if is_your_turn:
        return (
            "⏰ Время на ход истекло!\n\n"
            "Не волнуйтесь, бывает. Ход переходит к сопернику."
        )
    else:
        return (
            "⏰ Соперник не успел сделать ход.\n\n"
            "Теперь ваша очередь!"
        )


def get_afk_choice_message() -> str:
    """Get message for AFK choice prompt."""
    return (
        "😴 Кажется, вы отошли?\n\n"
        "Прошло несколько ходов без ответа. "
        "Что бы вы хотели сделать?\n\n"
        "Мы подождём, никуда не торопимся! 💙"
    )
