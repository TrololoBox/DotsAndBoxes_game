"""
Scoring logic for Dots and Boxes.

Handles score tracking and winner determination.
"""

from dataclasses import dataclass
from typing import Optional

from game.board import Board
from game.capture import count_player_squares


@dataclass
class GameScore:
    """Score state for a game."""
    player_a_id: str
    player_b_id: str
    player_a_score: int = 0
    player_b_score: int = 0
    
    def get_score(self, player_id: str) -> int:
        """Get score for a specific player."""
        if player_id == self.player_a_id:
            return self.player_a_score
        elif player_id == self.player_b_id:
            return self.player_b_score
        return 0
    
    def add_captures(self, player_id: str, count: int) -> None:
        """Add captured squares to a player's score."""
        if player_id == self.player_a_id:
            self.player_a_score += count
        elif player_id == self.player_b_id:
            self.player_b_score += count


@dataclass
class GameResult:
    """Final result of a game."""
    winner_id: Optional[str]  # None for draw
    player_a_score: int
    player_b_score: int
    is_draw: bool
    
    @property
    def has_winner(self) -> bool:
        return self.winner_id is not None


def calculate_result(board: Board, player_a_id: str, player_b_id: str) -> GameResult:
    """
    Calculate the final game result from board state.
    
    Args:
        board: Completed board state
        player_a_id: First player's ID
        player_b_id: Second player's ID
    
    Returns:
        GameResult with winner and scores
    """
    score_a = count_player_squares(board, player_a_id)
    score_b = count_player_squares(board, player_b_id)
    
    if score_a > score_b:
        winner = player_a_id
        is_draw = False
    elif score_b > score_a:
        winner = player_b_id
        is_draw = False
    else:
        winner = None
        is_draw = True
    
    return GameResult(
        winner_id=winner,
        player_a_score=score_a,
        player_b_score=score_b,
        is_draw=is_draw,
    )
