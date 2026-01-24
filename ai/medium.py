"""
Medium bot for Dots and Boxes.

Uses basic heuristics to avoid obvious mistakes.
Takes captures when available, avoids giving 3rd edges.
"""

import random
from typing import Optional

from game.board import Board
from ai.bot_interface import BotInterface, BotDifficulty


class MediumBot(BotInterface):
    """
    Medium difficulty bot.
    
    Behavior:
    - Always takes available captures
    - Avoids placing 3rd edge (giving opponent easy capture)
    - Random selection among "safe" moves
    - Falls back to risky moves when no safe options
    """
    
    @property
    def difficulty(self) -> BotDifficulty:
        return BotDifficulty.MEDIUM
    
    def choose_edge(self, board: Board) -> Optional[str]:
        """Choose an edge using basic heuristics."""
        legal_moves = self.get_legal_moves(board)
        
        if not legal_moves:
            return None
        
        # Priority 1: Take any available captures
        capture_moves = self._find_all_capture_moves(board, legal_moves)
        if capture_moves:
            return random.choice(capture_moves)
        
        # Priority 2: Find safe moves (don't give opponent a capture)
        safe_moves = self._find_safe_moves(board, legal_moves)
        if safe_moves:
            return random.choice(safe_moves)
        
        # Priority 3: Pick the least damaging move
        return self._pick_least_damaging(board, legal_moves)
    
    def _find_all_capture_moves(self, board: Board, moves: list[str]) -> list[str]:
        """Find all moves that would capture a square."""
        captures = []
        for edge_id in moves:
            if self._would_capture(board, edge_id):
                captures.append(edge_id)
        return captures
    
    def _would_capture(self, board: Board, edge_id: str) -> bool:
        """Check if placing an edge would capture a square."""
        adjacent_squares = board.get_adjacent_squares(edge_id)
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                if occupied == 3:
                    return True
        
        return False
    
    def _find_safe_moves(self, board: Board, moves: list[str]) -> list[str]:
        """Find moves that don't give opponent an easy capture."""
        safe = []
        for edge_id in moves:
            if not self._gives_capture(board, edge_id):
                safe.append(edge_id)
        return safe
    
    def _gives_capture(self, board: Board, edge_id: str) -> bool:
        """Check if placing an edge would create a 3-edge square for opponent."""
        adjacent_squares = board.get_adjacent_squares(edge_id)
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                # If 2 edges occupied, placing this creates a 3-edge square
                if occupied == 2:
                    return True
        
        return False
    
    def _pick_least_damaging(self, board: Board, moves: list[str]) -> str:
        """Pick the move that gives opponent the fewest easy captures."""
        # Score each move by how many squares it opens up
        scores = []
        for edge_id in moves:
            damage = self._count_damage(board, edge_id)
            scores.append((damage, edge_id))
        
        # Sort by damage (ascending) and pick from lowest
        scores.sort(key=lambda x: x[0])
        min_damage = scores[0][0]
        best_moves = [eid for dmg, eid in scores if dmg == min_damage]
        
        return random.choice(best_moves)
    
    def _count_damage(self, board: Board, edge_id: str) -> int:
        """Count how many squares would be opened for opponent."""
        damage = 0
        adjacent_squares = board.get_adjacent_squares(edge_id)
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                if occupied == 2:
                    damage += 1
        
        return damage
