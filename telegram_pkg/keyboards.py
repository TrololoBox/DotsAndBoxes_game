"""
Inline keyboard generation for all bot screens.

GRID LAYOUT RULES:
For NxN squares, keyboard is (2*N+1) x (2*N+1) matrix.

Cell type by coordinates (r, c):
- DOT:      r%2==0 and c%2==0  -> ⚫️ (non-clickable)
- H_EDGE:   r%2==0 and c%2==1  -> ⬜️/🟦/🟥 (clickable if empty)
- V_EDGE:   r%2==1 and c%2==0  -> ⬜️/🟦/🟥 (clickable if empty)
- SQUARE:   r%2==1 and c%2==1  -> 🟧/emoji (non-clickable)
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional, Dict

from telegram_pkg.callback_parser import (
    cb_menu, cb_mode, cb_size, cb_diff, cb_rematch,
    cb_cancel_queue, cb_afk
)
from telegram_pkg.messages import (
    BTN_PLAY, BTN_PROFILE, BTN_SETTINGS, BTN_SUPPORT, BTN_BACK,
    BTN_PVE, BTN_PVP_WORLD, BTN_PVP_FRIEND,
    BTN_EASY, BTN_MEDIUM, BTN_HARD,
    BTN_REMATCH, BTN_TO_MENU, BTN_CONTINUE_BOT, BTN_SURRENDER,
    BTN_CANCEL_QUEUE, BTN_WATCH_AD
)
from game.board import Board


# Callback data generators for grid cells
def cb_edge_h(r: int, c: int) -> str:
    """Callback for horizontal edge at matrix position (r, c)."""
    return f"e:h:{r}:{c}"


def cb_edge_v(r: int, c: int) -> str:
    """Callback for vertical edge at matrix position (r, c)."""
    return f"e:v:{r}:{c}"


def cb_noop(reason: str) -> str:
    """Callback for non-clickable cells."""
    return f"noop:{reason}"


# Visual symbols
SYM_DOT = "⚫"
SYM_EMPTY_H_EDGE = "➖"  # Horizontal empty edge
SYM_EMPTY_V_EDGE = "│"   # Vertical empty edge (narrower to fit)
SYM_EDGE_PLAYER_A = "🟦"
SYM_EDGE_PLAYER_B = "🟥"
SYM_EMPTY_SQUARE = "🟧"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_PLAY, callback_data=cb_menu("play"))],
        [
            InlineKeyboardButton(BTN_PROFILE, callback_data=cb_menu("profile")),
            InlineKeyboardButton(BTN_SETTINGS, callback_data=cb_menu("settings")),
        ],
        [InlineKeyboardButton(BTN_SUPPORT, callback_data=cb_menu("support"))],
    ])


def play_mode_keyboard() -> InlineKeyboardMarkup:
    """Game mode selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_PVE, callback_data=cb_mode("pve"))],
        [InlineKeyboardButton(BTN_PVP_WORLD, callback_data=cb_mode("pvp_world"))],
        [InlineKeyboardButton(BTN_PVP_FRIEND, callback_data=cb_mode("pvp_friend"))],
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("main"))],
    ])


def board_size_keyboard() -> InlineKeyboardMarkup:
    """Board size selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("3×3 (9 квадратов)", callback_data=cb_size(3))],
        [InlineKeyboardButton("4×4 (16 квадратов)", callback_data=cb_size(4))],
        [InlineKeyboardButton("5×5 (25 квадратов)", callback_data=cb_size(5))],
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("play"))],
    ])


def difficulty_keyboard() -> InlineKeyboardMarkup:
    """Bot difficulty selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_EASY, callback_data=cb_diff("easy"))],
        [InlineKeyboardButton(BTN_MEDIUM, callback_data=cb_diff("medium"))],
        [InlineKeyboardButton(BTN_HARD, callback_data=cb_diff("hard"))],
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("play"))],
    ])


def queue_keyboard() -> InlineKeyboardMarkup:
    """Queue waiting keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_CANCEL_QUEUE, callback_data=cb_cancel_queue())],
    ])


def game_board_keyboard(
    board: Board,
    player_a_id: str,
    player_b_id: str,
    player_emojis: Optional[Dict[str, str]] = None,
) -> InlineKeyboardMarkup:
    """
    Generate game board inline keyboard as proper grid.
    
    Grid size: (2*N+1) x (2*N+1) where N = board size in squares.
    
    Cell types by (row, col):
    - DOT:      row%2==0 and col%2==0
    - H_EDGE:   row%2==0 and col%2==1
    - V_EDGE:   row%2==1 and col%2==0
    - SQUARE:   row%2==1 and col%2==1
    """
    n = board.width  # Assuming square board
    grid_size = 2 * n + 1
    
    keyboard = []
    
    for r in range(grid_size):
        row_buttons = []
        
        for c in range(grid_size):
            is_even_row = r % 2 == 0
            is_even_col = c % 2 == 0
            
            if is_even_row and is_even_col:
                # DOT - non-clickable
                row_buttons.append(InlineKeyboardButton(
                    SYM_DOT,
                    callback_data=cb_noop("dot"),
                ))
            
            elif is_even_row and not is_even_col:
                # HORIZONTAL EDGE
                # Convert grid coords to board edge coords
                edge_row = r // 2
                edge_col = c // 2
                edge_id = f"h_{edge_row}_{edge_col}"
                edge = board.get_edge(edge_id)
                
                if edge and edge.is_occupied:
                    # Occupied edge
                    if edge.owner == player_a_id:
                        symbol = SYM_EDGE_PLAYER_A
                    else:
                        symbol = SYM_EDGE_PLAYER_B
                    row_buttons.append(InlineKeyboardButton(
                        symbol,
                        callback_data=cb_noop("occupied"),
                    ))
                else:
                    # Empty edge - clickable
                    row_buttons.append(InlineKeyboardButton(
                        SYM_EMPTY_H_EDGE,
                        callback_data=cb_edge_h(r, c),
                    ))
            
            elif not is_even_row and is_even_col:
                # VERTICAL EDGE
                edge_row = r // 2
                edge_col = c // 2
                edge_id = f"v_{edge_row}_{edge_col}"
                edge = board.get_edge(edge_id)
                
                if edge and edge.is_occupied:
                    # Occupied edge
                    if edge.owner == player_a_id:
                        symbol = SYM_EDGE_PLAYER_A
                    else:
                        symbol = SYM_EDGE_PLAYER_B
                    row_buttons.append(InlineKeyboardButton(
                        symbol,
                        callback_data=cb_noop("occupied"),
                    ))
                else:
                    # Empty edge - clickable
                    row_buttons.append(InlineKeyboardButton(
                        SYM_EMPTY_V_EDGE,
                        callback_data=cb_edge_v(r, c),
                    ))
            
            else:
                # SQUARE (odd row, odd col)
                square_row = r // 2
                square_col = c // 2
                square = board.get_square(square_row, square_col)
                
                if square and square.is_captured:
                    # Captured square - show owner's emoji
                    emoji = player_emojis.get(square.owner, SYM_EMPTY_SQUARE) if player_emojis else SYM_EMPTY_SQUARE
                    row_buttons.append(InlineKeyboardButton(
                        emoji,
                        callback_data=cb_noop("square"),
                    ))
                else:
                    # Empty square target
                    row_buttons.append(InlineKeyboardButton(
                        SYM_EMPTY_SQUARE,
                        callback_data=cb_noop("square"),
                    ))
        
        keyboard.append(row_buttons)
    
    # Add leave game button at the bottom
    keyboard.append([
        InlineKeyboardButton("🚪 Покинуть игру", callback_data="leave"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


def post_game_keyboard(can_rematch: bool = True) -> InlineKeyboardMarkup:
    """Post-game keyboard with rematch and menu options."""
    buttons = []
    
    if can_rematch:
        buttons.append([
            InlineKeyboardButton(BTN_REMATCH, callback_data=cb_rematch()),
            InlineKeyboardButton(BTN_TO_MENU, callback_data=cb_menu("main")),
        ])
        buttons.append([
            InlineKeyboardButton(BTN_WATCH_AD, callback_data=cb_noop("ad")),  # Stub
        ])
    else:
        buttons.append([
            InlineKeyboardButton(BTN_TO_MENU, callback_data=cb_menu("main")),
        ])
    
    return InlineKeyboardMarkup(buttons)


def afk_choice_keyboard() -> InlineKeyboardMarkup:
    """AFK choice keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_CONTINUE_BOT, callback_data=cb_afk("bot"))],
        [InlineKeyboardButton(BTN_SURRENDER, callback_data=cb_afk("surrender"))],
    ])


def back_keyboard(destination: str = "main") -> InlineKeyboardMarkup:
    """Simple back button keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu(destination))],
    ])
