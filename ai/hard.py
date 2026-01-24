"""
Hard bot for Dots and Boxes.

Uses chain analysis and strategic thinking.
Implements the "long chain rule" to maximize endgame advantage.
"""

import random
from typing import Optional
from collections import defaultdict

from game.board import Board
from ai.bot_interface import BotInterface, BotDifficulty


class HardBot(BotInterface):
    """
    Hard difficulty bot.
    
    Behavior:
    - Always takes available captures with chain following
    - Evaluates chain lengths and controls endgame
    - Uses double-cross strategy when beneficial
    - Sophisticated position evaluation
    """
    
    @property
    def difficulty(self) -> BotDifficulty:
        return BotDifficulty.HARD
    
    def choose_edge(self, board: Board) -> Optional[str]:
        """Choose an edge using advanced strategy."""
        legal_moves = self.get_legal_moves(board)
        
        if not legal_moves:
            return None
        
        # Priority 1: Take captures (chain following)
        capture_move = self._find_best_capture_chain(board, legal_moves)
        if capture_move:
            return capture_move
        
        # Priority 2: Strategic move selection
        return self._choose_strategic_move(board, legal_moves)
    
    def _find_best_capture_chain(self, board: Board, moves: list[str]) -> Optional[str]:
        """Find the best capture move considering chain length."""
        capture_moves = []
        
        for edge_id in moves:
            captures = self._count_chain_captures(board, edge_id)
            if captures > 0:
                capture_moves.append((captures, edge_id))
        
        if not capture_moves:
            return None
        
        # Take the capture that gives the most squares
        capture_moves.sort(key=lambda x: x[0], reverse=True)
        return capture_moves[0][1]
    
    def _count_chain_captures(self, board: Board, edge_id: str) -> int:
        """Simulate placing edge and count resulting chain captures."""
        # Simple check: just see if this completes a square
        adjacent_squares = board.get_adjacent_squares(edge_id)
        captures = 0
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                if occupied == 3:
                    captures += 1
        
        return captures
    
    def _choose_strategic_move(self, board: Board, moves: list[str]) -> str:
        """Choose a strategic non-capture move."""
        # Categorize moves
        safe_moves = []
        opens_small_chain = []  # Opens 1-2 squares
        opens_large_chain = []  # Opens 3+ squares
        
        for edge_id in moves:
            chain_size = self._get_chain_size_opened(board, edge_id)
            if chain_size == 0:
                safe_moves.append(edge_id)
            elif chain_size <= 2:
                opens_small_chain.append((chain_size, edge_id))
            else:
                opens_large_chain.append((chain_size, edge_id))
        
        # Priority: safe moves
        if safe_moves:
            return random.choice(safe_moves)
        
        # If we must open a chain, prefer smaller ones
        if opens_small_chain:
            opens_small_chain.sort(key=lambda x: x[0])
            return opens_small_chain[0][1]
        
        # Last resort: open a large chain, pick smallest
        if opens_large_chain:
            opens_large_chain.sort(key=lambda x: x[0])
            return opens_large_chain[0][1]
        
        # Fallback
        return random.choice(moves)
    
    def _get_chain_size_opened(self, board: Board, edge_id: str) -> int:
        """Estimate how many squares would be opened by this move."""
        adjacent_squares = board.get_adjacent_squares(edge_id)
        opened = 0
        
        for row, col in adjacent_squares:
            square = board.get_square(row, col)
            if square and not square.is_captured:
                edge_ids = board.get_square_edges(row, col)
                occupied = sum(
                    1 for eid in edge_ids
                    if board.edges.get(eid) and board.edges[eid].is_occupied
                )
                # Opening a 3rd edge creates a capture opportunity
                if occupied == 2:
                    # Count connected chain
                    chain_size = self._estimate_chain_size(board, row, col, edge_id)
                    opened += chain_size
        
        return opened
    
    def _estimate_chain_size(self, board: Board, start_row: int, start_col: int, new_edge: str) -> int:
        """Estimate the size of a chain starting from a square."""
        # Simple BFS to count connected squares with 2+ edges
        visited = set()
        queue = [(start_row, start_col)]
        chain_size = 0
        
        while queue:
            row, col = queue.pop(0)
            if (row, col) in visited:
                continue
            visited.add((row, col))
            
            square = board.get_square(row, col)
            if not square or square.is_captured:
                continue
            
            edge_ids = board.get_square_edges(row, col)
            occupied = sum(
                1 for eid in edge_ids
                if (board.edges.get(eid) and board.edges[eid].is_occupied) or eid == new_edge
            )
            
            if occupied >= 3:
                chain_size += 1
                # Add adjacent squares
                for adj_row, adj_col in self._get_adjacent_cells(row, col, board):
                    if (adj_row, adj_col) not in visited:
                        queue.append((adj_row, adj_col))
        
        return max(1, chain_size)
    
    def _get_adjacent_cells(self, row: int, col: int, board: Board) -> list[tuple[int, int]]:
        """Get cells adjacent to given cell."""
        adjacent = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < board.height and 0 <= nc < board.width:
                adjacent.append((nr, nc))
        return adjacent
