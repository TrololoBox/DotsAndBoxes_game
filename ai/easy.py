"""
Easy bot for Dots and Boxes.

Makes random moves with occasional awareness of captures.
Designed to be easily beatable for new players.
"""

import random
from typing import Optional

from game.board import Board
from ai.bot_interface import BotInterface, BotDifficulty


class EasyBot(BotInterface):
    """
    Easy difficulty bot.
    
    Behavior:
    - Mostly random edge selection
    - Small chance (20%) to take an obvious capture
    - Never avoids giving captures to opponent
    """
    
    CAPTURE_AWARENESS = 0.2  # 20% chance to notice a capture opportunity
    
    @property
    def difficulty(self) -> BotDifficulty:
        return BotDifficulty.EASY
    
    def choose_edge(self, board: Board) -> Optional[str]:
        """Choose a mostly random edge."""
        legal_moves = self.get_legal_moves(board)
        
        if not legal_moves:
            return None
        
        # Sometimes check for easy captures
        if random.random() < self.CAPTURE_AWARENESS:
            capture_move = self._find_capture_move(board, legal_moves)
            if capture_move:
                return capture_move
        
        # Otherwise, pick randomly
        return random.choice(legal_moves)
    
    def _find_capture_move(self, board: Board, moves: list[str]) -> Optional[str]:
        """Find a move that would capture a square."""
        for edge_id in moves:
            if self._would_capture(board, edge_id):
                return edge_id
        return None
    
    def _would_capture(self, board: Board, edge_id: str) -> bool:
        """Check if placing an edge would capture a square."""
        adjacent_squares = board.get_adjacent_squares(edge_id)
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                # Count occupied edges around this square
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                # If 3 edges are occupied, placing this one completes the square
                if occupied == 3:
                    return True
        
        return False
