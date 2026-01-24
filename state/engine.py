"""
Authoritative game state engine.

All state mutations for rooms must go through this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

from game.turn import apply_turn, TurnError, TurnResult
from game.edge_numbering import get_edge_by_number
from state.rooms import Room, RoomState
from state.logging_utils import log_event
from timers.turn_timer import reset_timeout_counter


logger = logging.getLogger(__name__)


ERROR_ROOM_NOT_FOUND = "room_not_found"
ERROR_NOT_IN_ROOM = "not_in_room"
ERROR_ROOM_INACTIVE = "room_inactive"
ERROR_GAME_FINISHED = "game_finished"
ERROR_STALE_CALLBACK = "stale_callback"
ERROR_NOT_YOUR_TURN = "not_your_turn"
ERROR_EDGE_OCCUPIED = "edge_occupied"
ERROR_INVALID_EDGE = "invalid_edge"
ERROR_INVALID_NUMBER = "invalid_number"
ERROR_INVALID_PAGE = "invalid_page"
ERROR_ACTION_REJECTED = "action_rejected"


@dataclass
class EngineResult:
    """Result of a state mutation attempt."""
    ok: bool
    error_code: Optional[str] = None
    turn_result: Optional[TurnResult] = None
    game_over: bool = False
    state_version: Optional[int] = None
    move_number: Optional[int] = None


def _touch(room: Room) -> None:
    room.last_activity_at = datetime.now()


def _bump_version(room: Room) -> None:
    room.state_version += 1
    room.turn_version = room.state_version


def start_game(room: Room) -> EngineResult:
    """Start a room and initialize state."""
    if room.state not in {RoomState.CREATED, RoomState.WAITING}:
        return EngineResult(ok=False, error_code=ERROR_ACTION_REJECTED)

    room.start_game()
    room.move_number = 0
    _bump_version(room)
    _touch(room)

    log_event(
        logger,
        logging.INFO,
        "room_started",
        game_id=room.id,
        room_id=room.id,
        state=room.state.value,
        state_version=room.state_version,
        move_number=room.move_number,
    )
    return EngineResult(
        ok=True,
        state_version=room.state_version,
        move_number=room.move_number,
    )


def end_game(room: Room, reason: str, detail: Optional[str] = None) -> None:
    """End a game via a single path."""
    room.state = RoomState.FINISHED if reason == "completed" else RoomState.ABORTED
    room.completed_at = datetime.now()
    room.end_reason = reason
    room.end_reason_detail = detail
    _bump_version(room)
    _touch(room)

    log_event(
        logger,
        logging.INFO,
        "room_ended",
        game_id=room.id,
        room_id=room.id,
        reason=reason,
        detail=detail,
        state=room.state.value,
        state_version=room.state_version,
        move_number=room.move_number,
    )


def _validate_room_for_action(
    room: Room,
    user_id: int,
    expected_version: Optional[int],
) -> Optional[str]:
    if room.state == RoomState.FINISHED:
        return ERROR_GAME_FINISHED
    if room.state != RoomState.ACTIVE:
        return ERROR_ROOM_INACTIVE
    if expected_version is None:
        return ERROR_STALE_CALLBACK
    if expected_version is not None and expected_version != room.state_version:
        return ERROR_STALE_CALLBACK
    if user_id not in {room.player_a_id, room.player_b_id}:
        return ERROR_NOT_IN_ROOM
    return None


def apply_edge_move(
    room: Room,
    user_id: int,
    edge_id: str,
    expected_version: Optional[int],
) -> EngineResult:
    """Apply an edge move after validations."""
    error = _validate_room_for_action(room, user_id, expected_version)
    if error:
        _log_reject(room, user_id, error, expected_version)
        return EngineResult(ok=False, error_code=error, state_version=room.state_version)

    if not room.is_player_turn(user_id):
        _log_reject(room, user_id, ERROR_NOT_YOUR_TURN, expected_version)
        return EngineResult(ok=False, error_code=ERROR_NOT_YOUR_TURN, state_version=room.state_version)

    player_id_str = str(user_id)
    other_player_str = str(room.other_player_id) if room.other_player_id else "bot"

    result = apply_turn(
        board=room.board,
        player_id=player_id_str,
        edge_id=edge_id,
        current_player=str(room.current_player_id),
        other_player=other_player_str,
    )

    if not result.success:
        error_code = ERROR_INVALID_EDGE
        if result.error == TurnError.EDGE_OCCUPIED:
            error_code = ERROR_EDGE_OCCUPIED
        elif result.error == TurnError.NOT_YOUR_TURN:
            error_code = ERROR_NOT_YOUR_TURN
        _log_reject(room, user_id, error_code, expected_version)
        return EngineResult(ok=False, error_code=error_code, state_version=room.state_version)

    room.move_number += 1
    _touch(room)
    reset_timeout_counter(room)

    if result.game_over:
        end_game(room, reason="completed")
        log_event(
            logger,
            logging.INFO,
            "move_applied",
            game_id=room.id,
            room_id=room.id,
            user_id=user_id,
            move_number=room.move_number,
            state_version=room.state_version,
            edge_id=edge_id,
            captures=len(result.captures),
            extra_turn=result.extra_turn,
            game_over=True,
        )
        return EngineResult(
            ok=True,
            turn_result=result,
            game_over=True,
            state_version=room.state_version,
            move_number=room.move_number,
        )

    _bump_version(room)

    if result.extra_turn:
        room.keep_current_player()
    else:
        room.switch_player()

    _touch(room)

    log_event(
        logger,
        logging.INFO,
        "move_applied",
        game_id=room.id,
        room_id=room.id,
        user_id=user_id,
        move_number=room.move_number,
        state_version=room.state_version,
        edge_id=edge_id,
        captures=len(result.captures),
        extra_turn=result.extra_turn,
    )

    return EngineResult(
        ok=True,
        turn_result=result,
        game_over=False,
        state_version=room.state_version,
        move_number=room.move_number,
    )


def apply_bot_edge(
    room: Room,
    edge_id: str,
) -> EngineResult:
    """Apply a bot edge move with authoritative updates."""
    if room.state != RoomState.ACTIVE:
        _log_reject(room, user_id="bot", reason=ERROR_ROOM_INACTIVE, expected_version=None)
        return EngineResult(ok=False, error_code=ERROR_ROOM_INACTIVE, state_version=room.state_version)

    if room.current_player_index != 1:
        _log_reject(room, user_id="bot", reason=ERROR_NOT_YOUR_TURN, expected_version=None)
        return EngineResult(ok=False, error_code=ERROR_NOT_YOUR_TURN, state_version=room.state_version)

    result = apply_turn(
        board=room.board,
        player_id="bot",
        edge_id=edge_id,
        current_player="bot",
        other_player=str(room.player_a_id),
    )

    if not result.success:
        error_code = ERROR_INVALID_EDGE
        if result.error == TurnError.EDGE_OCCUPIED:
            error_code = ERROR_EDGE_OCCUPIED
        _log_reject(room, user_id="bot", reason=error_code, expected_version=None)
        return EngineResult(ok=False, error_code=error_code, state_version=room.state_version)

    room.move_number += 1
    _touch(room)

    if result.game_over:
        end_game(room, reason="completed")
        log_event(
            logger,
            logging.INFO,
            "bot_move_applied",
            game_id=room.id,
            room_id=room.id,
            user_id="bot",
            move_number=room.move_number,
            state_version=room.state_version,
            edge_id=edge_id,
            captures=len(result.captures),
            extra_turn=result.extra_turn,
            game_over=True,
        )
        return EngineResult(
            ok=True,
            turn_result=result,
            game_over=True,
            state_version=room.state_version,
            move_number=room.move_number,
        )

    _bump_version(room)

    if result.extra_turn:
        room.keep_current_player()
    else:
        room.switch_player()

    _touch(room)

    log_event(
        logger,
        logging.INFO,
        "bot_move_applied",
        game_id=room.id,
        room_id=room.id,
        user_id="bot",
        move_number=room.move_number,
        state_version=room.state_version,
        edge_id=edge_id,
        captures=len(result.captures),
        extra_turn=result.extra_turn,
    )

    return EngineResult(
        ok=True,
        turn_result=result,
        game_over=False,
        state_version=room.state_version,
        move_number=room.move_number,
    )


def apply_numbered_move(
    room: Room,
    user_id: int,
    edge_number: Optional[int],
    expected_version: Optional[int],
) -> EngineResult:
    """Apply a numeric move after validations."""
    if edge_number is None:
        _log_reject(room, user_id, ERROR_INVALID_NUMBER, expected_version)
        return EngineResult(ok=False, error_code=ERROR_INVALID_NUMBER, state_version=room.state_version)

    edge_id = get_edge_by_number(room.board, edge_number)
    if not edge_id:
        _log_reject(room, user_id, ERROR_INVALID_NUMBER, expected_version)
        return EngineResult(ok=False, error_code=ERROR_INVALID_NUMBER, state_version=room.state_version)

    return apply_edge_move(room, user_id, edge_id, expected_version)


def update_page(
    room: Room,
    user_id: int,
    page: Optional[int],
    expected_version: Optional[int],
    max_page: int,
) -> EngineResult:
    """Update pagination state with validation."""
    error = _validate_room_for_action(room, user_id, expected_version)
    if error:
        _log_reject(room, user_id, error, expected_version)
        return EngineResult(ok=False, error_code=error, state_version=room.state_version)

    if page is None or page < 0 or page > max_page:
        _log_reject(room, user_id, ERROR_INVALID_PAGE, expected_version)
        return EngineResult(ok=False, error_code=ERROR_INVALID_PAGE, state_version=room.state_version)

    room.current_page = page
    _bump_version(room)
    _touch(room)

    log_event(
        logger,
        logging.INFO,
        "page_updated",
        game_id=room.id,
        room_id=room.id,
        user_id=user_id,
        page=page,
        state_version=room.state_version,
        move_number=room.move_number,
    )

    return EngineResult(ok=True, state_version=room.state_version, move_number=room.move_number)


def abandon_room(room: Room, user_id: int, reason: str) -> None:
    """Abort the room explicitly."""
    end_game(room, reason="aborted", detail=reason)
    log_event(
        logger,
        logging.INFO,
        "room_aborted",
        game_id=room.id,
        room_id=room.id,
        user_id=user_id,
        reason=reason,
        state_version=room.state_version,
        move_number=room.move_number,
    )


def _log_reject(room: Room, user_id: object, reason: str, expected_version: Optional[int]) -> None:
    log_event(
        logger,
        logging.WARNING,
        "action_rejected",
        game_id=room.id,
        room_id=room.id,
        user_id=user_id,
        reason=reason,
        expected_version=expected_version,
        state_version=room.state_version,
        move_number=room.move_number,
    )
