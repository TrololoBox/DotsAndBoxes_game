"""
UX mapping for engine error codes to user-facing toasts.
"""

from __future__ import annotations

from telegram_pkg.toasts import (
    toast_game_finished,
    toast_not_in_room,
    toast_not_your_turn,
    toast_occupied_edge,
    toast_room_not_found,
    toast_stale_callback,
    toast_transition_state,
    toast_invalid_number,
    toast_invalid_edge,
    toast_invalid_page,
    toast_unknown_error,
)
from state import engine


def toast_for_error(code: str) -> str:
    """Map engine error codes to a deterministic toast message."""
    mapping = {
        engine.ERROR_ROOM_NOT_FOUND: toast_room_not_found(),
        engine.ERROR_NOT_IN_ROOM: toast_not_in_room(),
        engine.ERROR_ROOM_INACTIVE: toast_transition_state(),
        engine.ERROR_GAME_FINISHED: toast_game_finished(),
        engine.ERROR_STALE_CALLBACK: toast_stale_callback(),
        engine.ERROR_NOT_YOUR_TURN: toast_not_your_turn(),
        engine.ERROR_EDGE_OCCUPIED: toast_occupied_edge(),
        engine.ERROR_INVALID_EDGE: toast_invalid_edge(),
        engine.ERROR_INVALID_NUMBER: toast_invalid_number(),
        engine.ERROR_INVALID_PAGE: toast_invalid_page(),
        engine.ERROR_ACTION_REJECTED: toast_transition_state(),
    }
    return mapping.get(code, toast_unknown_error())
