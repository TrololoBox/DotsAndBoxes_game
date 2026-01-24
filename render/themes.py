"""
Rendering themes for board visualization.

Each theme defines colors for players, neutral elements, and background.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Theme:
    """Color theme for board rendering."""
    name: str
    display_name: str
    player_a: str  # Hex color for player A's edges
    player_b: str  # Hex color for player B's edges
    neutral: str   # Hex color for unoccupied edges
    background: str  # Hex color for background
    dot_color: str = "#333333"  # Color for dots
    text_color: str = "#333333"  # Color for text/labels
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    @property
    def player_a_rgb(self) -> Tuple[int, int, int]:
        return self.hex_to_rgb(self.player_a)
    
    @property
    def player_b_rgb(self) -> Tuple[int, int, int]:
        return self.hex_to_rgb(self.player_b)
    
    @property
    def neutral_rgb(self) -> Tuple[int, int, int]:
        return self.hex_to_rgb(self.neutral)
    
    @property
    def background_rgb(self) -> Tuple[int, int, int]:
        return self.hex_to_rgb(self.background)
    
    @property
    def dot_rgb(self) -> Tuple[int, int, int]:
        return self.hex_to_rgb(self.dot_color)


# Preset themes
THEMES = {
    "classic": Theme(
        name="classic",
        display_name="Классика",
        player_a="#2F80ED",
        player_b="#EB5757",
        neutral="#BDBDBD",
        background="#F2F2F2",
    ),
    "forest": Theme(
        name="forest",
        display_name="Лес",
        player_a="#219653",
        player_b="#F2994A",
        neutral="#BDBDBD",
        background="#F2F2F2",
    ),
    "night": Theme(
        name="night",
        display_name="Ночь",
        player_a="#56CCF2",
        player_b="#BB6BD9",
        neutral="#4F4F4F",
        background="#1B1B1B",
        dot_color="#FFFFFF",
        text_color="#FFFFFF",
    ),
}


def get_theme(name: str) -> Theme:
    """Get a theme by name, defaulting to classic."""
    return THEMES.get(name, THEMES["classic"])
