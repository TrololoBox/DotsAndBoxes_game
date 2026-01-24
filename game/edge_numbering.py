"""
Edge numbering utilities for numbered input mode.

Maps edge IDs to display numbers (1-100) and vice versa.
Numbering is deterministic: horizontal edges first (top to bottom, left to right),
then vertical edges (top to bottom, left to right).
"""

from typing import Dict, List, Optional, Tuple
from game.board import Board, EdgeOrientation


def get_edge_numbers(board: Board) -> Dict[str, int]:
    """
    Generate mapping from edge_id to display number.
    
    Numbering order (Interleaved):
    Row 0: Horizontals -> Verticals
    Row 1: Horizontals -> Verticals
    ...
    Last Row: Horizontals
    
    Returns:
        Dict mapping edge_id -> number (1-indexed)
    """
    edge_numbers = {}
    num = 1
    
    for row in range(board.height + 1):
        # 1. Horizontal edges in this row
        for col in range(board.width):
            edge_id = f"h_{row}_{col}"
            edge_numbers[edge_id] = num
            num += 1
            
        # 2. Vertical edges starting from this row (connecting to next)
        # Only if not the last row of dots
        if row < board.height:
            for col in range(board.width + 1):
                edge_id = f"v_{row}_{col}"
                edge_numbers[edge_id] = num
                num += 1
    
    return edge_numbers


def get_number_to_edge(board: Board) -> Dict[int, str]:
    """
    Generate reverse mapping from display number to edge_id.
    
    Returns:
        Dict mapping number -> edge_id
    """
    edge_numbers = get_edge_numbers(board)
    return {num: edge_id for edge_id, num in edge_numbers.items()}


def get_edge_by_number(board: Board, number: int) -> Optional[str]:
    """
    Get edge_id for a display number.
    
    Returns:
        edge_id string or None if number is out of range
    """
    mapping = get_number_to_edge(board)
    return mapping.get(number)


def get_number_for_edge(board: Board, edge_id: str) -> Optional[int]:
    """
    Get display number for an edge.
    
    Returns:
        Number (1-indexed) or None if edge not found
    """
    mapping = get_edge_numbers(board)
    return mapping.get(edge_id)


def get_edge_center_position(
    board: Board,
    edge_id: str,
    cell_size: int,
    margin: int,
) -> Optional[Tuple[int, int]]:
    """
    Calculate the center pixel position of an edge for number rendering.
    
    Args:
        board: Game board
        edge_id: Edge identifier (e.g., "h_0_0" or "v_0_0")
        cell_size: Pixel size of each cell
        margin: Margin around the board
    
    Returns:
        (x, y) center position or None if edge not found
    """
    parts = edge_id.split("_")
    if len(parts) != 3:
        return None
    
    orientation, row_str, col_str = parts
    try:
        row = int(row_str)
        col = int(col_str)
    except ValueError:
        return None
    
    if orientation == "h":
        # Horizontal edge: center is between two horizontal dots
        x = margin + col * cell_size + cell_size // 2
        y = margin + row * cell_size
    elif orientation == "v":
        # Vertical edge: center is between two vertical dots
        x = margin + col * cell_size
        y = margin + row * cell_size + cell_size // 2
    else:
        return None
    
    return (x, y)


def get_occupied_numbers(board: Board) -> List[int]:
    """
    Get list of numbers corresponding to occupied edges.
    
    Returns:
        List of numbers (1-indexed) that are already taken
    """
    edge_numbers = get_edge_numbers(board)
    occupied = []
    
    for edge_id, num in edge_numbers.items():
        edge = board.get_edge(edge_id)
        if edge and edge.is_occupied:
            occupied.append(num)
    
    return occupied


def get_free_numbers(board: Board) -> List[int]:
    """
    Get list of numbers corresponding to free edges.
    
    Returns:
        List of numbers (1-indexed) that are available
    """
    edge_numbers = get_edge_numbers(board)
    free = []
    
    for edge_id, num in edge_numbers.items():
        edge = board.get_edge(edge_id)
        if edge and not edge.is_occupied:
            free.append(num)
    
    return sorted(free)
