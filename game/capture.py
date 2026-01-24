"""
Capture detection for Dots and Boxes.

Determines which squares are captured after edge placement.
"""

from game.board import Board


def detect_captures(board: Board, edge_id: str, player_id: str) -> list[tuple[int, int]]:
    """
    Detect squares captured by placing an edge.
    
    Args:
        board: Current board state
        edge_id: The edge that was just placed
        player_id: The player who placed the edge
    
    Returns:
        List of (row, col) tuples for newly captured squares
    """
    captured = []
    
    # Get squares adjacent to the placed edge
    adjacent_squares = board.get_adjacent_squares(edge_id)
    
    for row, col in adjacent_squares:
        square = board.get_square(row, col)
        
        # Skip if already captured
        if square is None or square.is_captured:
            continue
        
        # Check if all 4 edges are now occupied
        if board.is_square_complete(row, col):
            # Capture the square for the player
            square.owner = player_id
            captured.append((row, col))
    
    return captured


def count_player_squares(board: Board, player_id: str) -> int:
    """Count squares captured by a specific player."""
    count = 0
    for row in board.squares:
        for square in row:
            if square.owner == player_id:
                count += 1
    return count
