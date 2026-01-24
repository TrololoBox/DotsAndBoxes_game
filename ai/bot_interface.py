"""
Bot interface and base class for PvE opponents.

All bots implement the same interface and only use public game state.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from game.board import Board


class BotDifficulty(Enum):
    """Bot difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BotInterface(ABC):
    """Abstract base class for all bot implementations."""
    
    @property
    @abstractmethod
    def difficulty(self) -> BotDifficulty:
        """Return the bot's difficulty level."""
        pass
    
    @abstractmethod
    def choose_edge(self, board: Board) -> Optional[str]:
        """
        Choose an edge to place.
        
        Args:
            board: Current game board state
        
        Returns:
            Edge ID to place, or None if no legal moves
        """
        pass
    
    def get_legal_moves(self, board: Board) -> list[str]:
        """Get all legal edge placements."""
        return board.get_available_edges()
