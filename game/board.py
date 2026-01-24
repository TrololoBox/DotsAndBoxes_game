"""
Board representation for Dots and Boxes.

The board is a grid of dots with edges between adjacent dots.
Squares are formed by completing all 4 edges around a cell.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EdgeOrientation(Enum):
    """Edge orientation on the board."""
    HORIZONTAL = "h"
    VERTICAL = "v"


@dataclass
class Edge:
    """Represents an edge between two dots."""
    orientation: EdgeOrientation
    row: int
    col: int
    owner: Optional[str] = None  # Player ID who placed this edge
    
    @property
    def edge_id(self) -> str:
        """Generate unique edge identifier."""
        return f"{self.orientation.value}_{self.row}_{self.col}"
    
    @property
    def is_occupied(self) -> bool:
        """Check if edge has been placed."""
        return self.owner is not None


@dataclass
class Square:
    """Represents a capturable square on the board."""
    row: int
    col: int
    owner: Optional[str] = None  # Player ID who captured this square
    
    @property
    def is_captured(self) -> bool:
        """Check if square has been captured."""
        return self.owner is not None


@dataclass
class Board:
    """
    Game board state.
    
    Dimensions are in squares (not dots).
    A 3x3 board has 3x3=9 squares, 4x3=12 dots, and 24 edges.
    """
    width: int  # Number of squares horizontally
    height: int  # Number of squares vertically
    edges: dict[str, Edge] = field(default_factory=dict)
    squares: list[list[Square]] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize edges and squares after dataclass creation."""
        if not self.edges:
            self._init_edges()
        if not self.squares:
            self._init_squares()
    
    def _init_edges(self) -> None:
        """Create all edges for the board."""
        # Horizontal edges: (height + 1) rows, width edges per row
        for row in range(self.height + 1):
            for col in range(self.width):
                edge = Edge(EdgeOrientation.HORIZONTAL, row, col)
                self.edges[edge.edge_id] = edge
        
        # Vertical edges: height rows, (width + 1) edges per row
        for row in range(self.height):
            for col in range(self.width + 1):
                edge = Edge(EdgeOrientation.VERTICAL, row, col)
                self.edges[edge.edge_id] = edge
    
    def _init_squares(self) -> None:
        """Create all squares for the board."""
        self.squares = [
            [Square(row, col) for col in range(self.width)]
            for row in range(self.height)
        ]
    
    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get edge by ID."""
        return self.edges.get(edge_id)
    
    def get_square(self, row: int, col: int) -> Optional[Square]:
        """Get square at position."""
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.squares[row][col]
        return None
    
    def get_available_edges(self) -> list[str]:
        """Get list of edge IDs that haven't been placed yet."""
        return [
            edge_id for edge_id, edge in self.edges.items()
            if not edge.is_occupied
        ]
    
    def get_square_edges(self, row: int, col: int) -> list[str]:
        """Get the 4 edge IDs that form a square."""
        return [
            f"h_{row}_{col}",      # Top edge
            f"h_{row + 1}_{col}",  # Bottom edge
            f"v_{row}_{col}",      # Left edge
            f"v_{row}_{col + 1}",  # Right edge
        ]
    
    def is_square_complete(self, row: int, col: int) -> bool:
        """Check if all 4 edges of a square are occupied."""
        edge_ids = self.get_square_edges(row, col)
        return all(
            self.edges.get(eid) and self.edges[eid].is_occupied
            for eid in edge_ids
        )
    
    def get_adjacent_squares(self, edge_id: str) -> list[tuple[int, int]]:
        """
        Get squares adjacent to an edge.
        
        Horizontal edges are adjacent to squares above and below.
        Vertical edges are adjacent to squares left and right.
        """
        edge = self.edges.get(edge_id)
        if not edge:
            return []
        
        adjacent = []
        
        if edge.orientation == EdgeOrientation.HORIZONTAL:
            # Square above (row - 1)
            if edge.row > 0:
                adjacent.append((edge.row - 1, edge.col))
            # Square below (row)
            if edge.row < self.height:
                adjacent.append((edge.row, edge.col))
        else:  # VERTICAL
            # Square left (col - 1)
            if edge.col > 0:
                adjacent.append((edge.row, edge.col - 1))
            # Square right (col)
            if edge.col < self.width:
                adjacent.append((edge.row, edge.col))
        
        return adjacent
    
    def place_edge(self, edge_id: str, player_id: str) -> bool:
        """
        Place an edge for a player.
        
        Returns True if placement was successful, False otherwise.
        """
        edge = self.edges.get(edge_id)
        if edge is None or edge.is_occupied:
            return False
        
        edge.owner = player_id
        return True
    
    def is_game_over(self) -> bool:
        """Check if all edges have been placed."""
        return all(edge.is_occupied for edge in self.edges.values())
    
    @property
    def total_squares(self) -> int:
        """Total number of squares on the board."""
        return self.width * self.height
    
    @property
    def total_edges(self) -> int:
        """Total number of edges on the board."""
        return len(self.edges)


def create_board(size: int) -> Board:
    """Create a square board of given size."""
    return Board(width=size, height=size)
