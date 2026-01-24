"""
Move validation utilities for Dots and Boxes.
"""

from game.board import Board
from game.turn import TurnError, validate_move


def is_valid_move(board: Board, edge_id: str) -> bool:
    """Check if placing an edge is a valid move."""
    return validate_move(board, edge_id) == TurnError.NONE


def get_legal_moves(board: Board) -> list[str]:
    """Get all legal edge IDs that can be placed."""
    return board.get_available_edges()
