"""
Callback data parsing and generation.

Format: action:param1:param2:...
Max length: 64 bytes (Telegram limit)

EDGE CALLBACK FORMAT:
- "e:h:<r>:<c>" for horizontal edges (matrix coordinates)
- "e:v:<r>:<c>" for vertical edges (matrix coordinates)

NOOP CALLBACK FORMAT:
- "noop:<reason>" where reason is: dot, square, occupied, ad
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class CallbackAction(Enum):
    """All callback action types."""
    # Menu navigation
    MENU = "menu"
    
    # Game setup
    MODE = "mode"
    SIZE = "size"
    DIFF = "diff"
    
    # In-game
    EDGE = "e"  # Edge placement
    NOOP = "noop"  # Non-interactive cells
    
    # Post-game
    REMATCH = "rm"
    
    # Queue
    CANCEL_QUEUE = "cq"
    
    # AFK
    AFK = "afk"
    
    # Invite
    INVITE = "inv"


@dataclass
class ParsedCallback:
    """Parsed callback data."""
    action: CallbackAction
    params: list[str]
    raw: str  # Original callback string
    
    @property
    def param1(self) -> Optional[str]:
        return self.params[0] if self.params else None
    
    @property
    def param2(self) -> Optional[str]:
        return self.params[1] if len(self.params) > 1 else None
    
    @property
    def param3(self) -> Optional[str]:
        return self.params[2] if len(self.params) > 2 else None
    
    @property
    def is_edge(self) -> bool:
        return self.action == CallbackAction.EDGE
    
    @property
    def is_noop(self) -> bool:
        return self.action == CallbackAction.NOOP
    
    @property
    def noop_reason(self) -> Optional[str]:
        """Get reason for noop callback (dot, square, occupied)."""
        if self.is_noop:
            return self.param1
        return None
    
    @property
    def edge_type(self) -> Optional[str]:
        """Get edge type: 'h' for horizontal, 'v' for vertical."""
        if self.is_edge:
            return self.param1
        return None
    
    @property
    def edge_matrix_row(self) -> Optional[int]:
        """Get matrix row of edge."""
        if self.is_edge and self.param2:
            return int(self.param2)
        return None
    
    @property
    def edge_matrix_col(self) -> Optional[int]:
        """Get matrix col of edge."""
        if self.is_edge and self.param3:
            return int(self.param3)
        return None


def parse_callback(data: str) -> ParsedCallback:
    """Parse callback data string into structured format."""
    parts = data.split(":")
    
    try:
        action = CallbackAction(parts[0])
    except ValueError:
        action = CallbackAction.NOOP
    
    params = parts[1:] if len(parts) > 1 else []
    
    return ParsedCallback(action=action, params=params, raw=data)


def matrix_to_edge_id(edge_type: str, matrix_row: int, matrix_col: int) -> str:
    """
    Convert matrix coordinates to board edge_id.
    
    For horizontal edge at matrix (r, c):
      board edge is h_{r//2}_{c//2}
    
    For vertical edge at matrix (r, c):
      board edge is v_{r//2}_{c//2}
    """
    if edge_type == "h":
        edge_row = matrix_row // 2
        edge_col = matrix_col // 2
        return f"h_{edge_row}_{edge_col}"
    else:  # "v"
        edge_row = matrix_row // 2
        edge_col = matrix_col // 2
        return f"v_{edge_row}_{edge_col}"


# Callback generators

def cb_menu(screen: str) -> str:
    """Generate menu navigation callback."""
    return f"menu:{screen}"


def cb_mode(mode: str) -> str:
    """Generate game mode selection callback."""
    return f"mode:{mode}"


def cb_size(size: int) -> str:
    """Generate board size selection callback."""
    return f"size:{size}"


def cb_diff(difficulty: str) -> str:
    """Generate difficulty selection callback."""
    return f"diff:{difficulty}"


def cb_rematch() -> str:
    """Generate rematch callback."""
    return "rm"


def cb_cancel_queue() -> str:
    """Generate cancel queue callback."""
    return "cq"


def cb_afk(choice: str) -> str:
    """Generate AFK choice callback."""
    return f"afk:{choice}"
