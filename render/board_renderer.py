"""
Board renderer using Pillow.

Generates PNG images of the game board state.
Rendering is deterministic: same input always produces identical output.
"""

import io
from dataclasses import dataclass
from typing import Optional, Dict

from PIL import Image, ImageDraw, ImageFont

from game.board import Board, EdgeOrientation
from render.themes import Theme, get_theme


@dataclass
class RenderConfig:
    """Configuration for board rendering."""
    cell_size: int = 80        # Pixels per square
    dot_radius: int = 8        # Radius of dots
    edge_thickness: int = 4    # Thickness of unoccupied edges
    occupied_thickness: int = 8  # Thickness of occupied edges
    margin: int = 40           # Margin around the board
    emoji_size: int = 32       # Size of emoji in captured squares
    font_size: int = 24        # Font size for labels


class BoardRenderer:
    """Renders game board as PNG image."""
    
    def __init__(
        self,
        board: Board,
        theme: Theme,
        config: Optional[RenderConfig] = None,
        player_a_id: str = "player_a",
        player_b_id: str = "player_b",
        player_emojis: Optional[Dict[str, str]] = None,
    ):
        self.board = board
        self.theme = theme
        self.config = config or RenderConfig()
        self.player_a_id = player_a_id
        self.player_b_id = player_b_id
        self.player_emojis = player_emojis or {}
        
        # Calculate image dimensions
        self.width = (
            self.board.width * self.config.cell_size +
            2 * self.config.margin
        )
        self.height = (
            self.board.height * self.config.cell_size +
            2 * self.config.margin
        )
    
    def _get_dot_position(self, row: int, col: int) -> tuple[int, int]:
        """Get pixel position of a dot."""
        x = self.config.margin + col * self.config.cell_size
        y = self.config.margin + row * self.config.cell_size
        return x, y
    
    def _get_edge_color(self, owner: Optional[str]) -> tuple[int, int, int]:
        """Get RGB color for an edge based on its owner."""
        if owner is None:
            return self.theme.neutral_rgb
        elif owner == self.player_a_id:
            return self.theme.player_a_rgb
        else:
            return self.theme.player_b_rgb
    
    def _get_square_center(self, row: int, col: int) -> tuple[int, int]:
        """Get pixel position of a square's center."""
        x = self.config.margin + col * self.config.cell_size + self.config.cell_size // 2
        y = self.config.margin + row * self.config.cell_size + self.config.cell_size // 2
        return x, y
    
    def render(self) -> bytes:
        """
        Render the board to PNG bytes.
        
        Returns:
            PNG image as bytes
        """
        # Create image with background
        image = Image.new('RGB', (self.width, self.height), self.theme.background_rgb)
        draw = ImageDraw.Draw(image)
        
        # Draw layers in order
        self._draw_squares(draw)
        self._draw_edges(draw)
        self._draw_dots(draw)
        self._draw_emojis(draw, image)
        
        # Convert to PNG bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
    
    def _draw_dots(self, draw: ImageDraw.Draw) -> None:
        """Draw dots at grid intersections."""
        r = self.config.dot_radius
        
        for row in range(self.board.height + 1):
            for col in range(self.board.width + 1):
                x, y = self._get_dot_position(row, col)
                draw.ellipse(
                    [x - r, y - r, x + r, y + r],
                    fill=self.theme.dot_rgb,
                )
    
    def _draw_edges(self, draw: ImageDraw.Draw) -> None:
        """Draw all edges with appropriate colors and thickness."""
        for edge_id, edge in self.board.edges.items():
            # Get start and end positions
            if edge.orientation == EdgeOrientation.HORIZONTAL:
                x1, y1 = self._get_dot_position(edge.row, edge.col)
                x2, y2 = self._get_dot_position(edge.row, edge.col + 1)
            else:  # VERTICAL
                x1, y1 = self._get_dot_position(edge.row, edge.col)
                x2, y2 = self._get_dot_position(edge.row + 1, edge.col)
            
            # Determine color and thickness
            color = self._get_edge_color(edge.owner)
            thickness = (
                self.config.occupied_thickness if edge.is_occupied
                else self.config.edge_thickness
            )
            
            draw.line([x1, y1, x2, y2], fill=color, width=thickness)
    
    def _draw_squares(self, draw: ImageDraw.Draw) -> None:
        """Draw captured squares with a subtle fill."""
        for row in range(self.board.height):
            for col in range(self.board.width):
                square = self.board.get_square(row, col)
                if square and square.is_captured:
                    # Get square bounds
                    x1, y1 = self._get_dot_position(row, col)
                    x2, y2 = self._get_dot_position(row + 1, col + 1)
                    
                    # Get owner color with transparency effect
                    color = self._get_edge_color(square.owner)
                    # Lighten the color for fill
                    fill_color = tuple(min(255, c + 80) for c in color)
                    
                    draw.rectangle([x1, y1, x2, y2], fill=fill_color)
    
    def _draw_emojis(self, draw: ImageDraw.Draw, image: Image.Image) -> None:
        """Draw emojis in captured squares."""
        # Note: Proper emoji rendering requires a font with emoji support
        # For simplicity, we'll draw a placeholder or use unicode
        for row in range(self.board.height):
            for col in range(self.board.width):
                square = self.board.get_square(row, col)
                if square and square.is_captured:
                    x, y = self._get_square_center(row, col)
                    emoji = self.player_emojis.get(square.owner, "⬤")
                    
                    # Try to draw text (emoji may render as placeholder)
                    try:
                        # Use default font
                        draw.text(
                            (x, y),
                            emoji,
                            fill=self.theme.dot_rgb,
                            anchor="mm",
                        )
                    except Exception:
                        # Fallback: draw a simple circle marker
                        r = 12
                        color = self._get_edge_color(square.owner)
                        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def render_board(
    board: Board,
    theme_name: str = "classic",
    player_a_id: str = "player_a",
    player_b_id: str = "player_b",
    player_emojis: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    Convenience function to render a board.
    
    Args:
        board: Game board to render
        theme_name: Name of theme to use
        player_a_id: ID of first player
        player_b_id: ID of second player
        player_emojis: Map of player IDs to emojis
    
    Returns:
        PNG image as bytes
    """
    theme = get_theme(theme_name)
    renderer = BoardRenderer(
        board=board,
        theme=theme,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        player_emojis=player_emojis,
    )
    return renderer.render()
