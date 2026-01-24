"""
Turn logic for Dots and Boxes.

Handles turn order, edge placement validation, and extra turns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from game.board import Board
from game.capture import detect_captures


class TurnError(Enum):
    """Possible errors when attempting a move."""
    NONE = "none"
    NOT_YOUR_TURN = "not_your_turn"
    EDGE_OCCUPIED = "edge_occupied"
    INVALID_EDGE = "invalid_edge"


@dataclass
class TurnResult:
    """Result of applying a turn."""
    success: bool
    error: TurnError
    captures: list[tuple[int, int]]  # Squares captured this turn
    extra_turn: bool  # Player gets another turn
    game_over: bool  # Game has ended
    next_player: Optional[str]  # Who plays next (None if game over)


def validate_move(board: Board, edge_id: str) -> TurnError:
    """
    Validate if an edge placement is legal.
    
    Args:
        board: Current board state
        edge_id: Edge to validate
    
    Returns:
        TurnError indicating validity
    """
    edge = board.get_edge(edge_id)
    
    if edge is None:
        return TurnError.INVALID_EDGE
    
    if edge.is_occupied:
        return TurnError.EDGE_OCCUPIED
    
    return TurnError.NONE


def apply_turn(
    board: Board,
    player_id: str,
    edge_id: str,
    current_player: str,
    other_player: str,
) -> TurnResult:
    """
    Apply a turn: place edge, check captures, determine next player.
    
    Args:
        board: Current board state (will be modified)
        player_id: Player making the move
        edge_id: Edge to place
        current_player: ID of player whose turn it is
        other_player: ID of the other player
    
    Returns:
        TurnResult with outcome of the turn
    """
    # Check if it's the player's turn
    if player_id != current_player:
        return TurnResult(
            success=False,
            error=TurnError.NOT_YOUR_TURN,
            captures=[],
            extra_turn=False,
            game_over=False,
            next_player=current_player,
        )
    
    # Validate the move
    error = validate_move(board, edge_id)
    if error != TurnError.NONE:
        return TurnResult(
            success=False,
            error=error,
            captures=[],
            extra_turn=False,
            game_over=False,
            next_player=current_player,
        )
    
    # Place the edge
    board.place_edge(edge_id, player_id)
    
    # Detect captures
    captures = detect_captures(board, edge_id, player_id)
    
    # Check if game is over
    game_over = board.is_game_over()
    
    # Determine next player: extra turn if captured, else switch
    if captures:
        extra_turn = True
        next_player = current_player if not game_over else None
    else:
        extra_turn = False
        next_player = other_player if not game_over else None
    
    return TurnResult(
        success=True,
        error=TurnError.NONE,
        captures=captures,
        extra_turn=extra_turn,
        game_over=game_over,
        next_player=next_player,
    )
