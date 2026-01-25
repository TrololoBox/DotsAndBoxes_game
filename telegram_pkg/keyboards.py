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

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import Optional, Dict

from telegram_pkg.callback_parser import (
    cb_menu, cb_mode, cb_size, cb_diff, cb_rematch,
    cb_cancel_queue, cb_afk, cb_num, cb_page
)
from telegram_pkg.messages import (
    BTN_PLAY, BTN_PROFILE, BTN_SETTINGS, BTN_SUPPORT, BTN_BACK,
    BTN_PVE, BTN_PVP_WORLD, BTN_PVP_FRIEND,
    BTN_EASY, BTN_MEDIUM, BTN_HARD,
    BTN_REMATCH, BTN_TO_MENU, BTN_CONTINUE_BOT, BTN_SURRENDER,
    BTN_CANCEL_QUEUE, BTN_WATCH_AD
)
from game.board import Board
from game.edge_numbering import get_number_for_edge


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


def persistent_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom menu keyboard (can be collapsed by user)."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 Меню"), KeyboardButton("💝 Поддержать")],
            [KeyboardButton("🗑 Очистить чат")],
        ],
        resize_keyboard=True,
    )


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
        [InlineKeyboardButton("3×4 (12 квадратов)", callback_data=cb_size(10304))],
        [InlineKeyboardButton("3×5 (15 квадратов)", callback_data=cb_size(10305))],
        [InlineKeyboardButton("4×4 (16 квадратов)", callback_data=cb_size(10404))],
        [InlineKeyboardButton("5×5 (🔢 Цифры)", callback_data=cb_size(10505))],
        [InlineKeyboardButton("6×6 (🔢 Цифры)", callback_data=cb_size(10606))],
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
    """
    width = board.width
    height = board.height
    grid_width = 2 * width + 1
    grid_height = 2 * height + 1
    
    keyboard = []
    
    for r in range(grid_height):
        row_buttons = []
        
        for c in range(grid_width):
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


def numbered_edge_keyboard(board: Board) -> InlineKeyboardMarkup:
    """
    Generate numeric keypad for edge selection.
    
    Shows buttons 1 to N, where N is total edges.
    Occupied edges are marked and non-clickable.
    """
    from game.edge_numbering import get_edge_numbers
    
    edge_numbers = get_edge_numbers(board)
    max_edges = len(edge_numbers)
    
    buttons = []
    row = []
    
    # Sort edges by number to display 1..N
    sorted_edges = sorted(edge_numbers.items(), key=lambda x: x[1])
    
    for edge_id, number in sorted_edges:
        edge = board.get_edge(edge_id)
        is_occupied = edge and edge.is_occupied
        
        text = str(number)
        if is_occupied:
            text = "✓"
            callback = cb_noop("occupied")
        else:
            callback = cb_num(number)
        
        row.append(InlineKeyboardButton(text, callback_data=callback))
        
        if len(row) == 8:  # 8 columns max
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    # Add leave game button at the bottom
    buttons.append([
        InlineKeyboardButton("🚪 Покинуть игру", callback_data="leave"),
    ])
    
    return InlineKeyboardMarkup(buttons)



def lines_keyboard(board: Board, player_a_id: str, player_b_id: Optional[str] = None, page: int = 0) -> InlineKeyboardMarkup:
    """
    Generate keyboard with lines only (for large boards).
    Shows buttons as horizontal strips. Supports pagination.
    """
    buttons = []
    all_rows = []
    
    # 1. Generate all rows of buttons
    # Iterate through board rows
    for r in range(board.height + 1):
        # Horizontal edges (width buttons)
        h_row = []
        for c in range(board.width):
            edge_id = f"h_{r}_{c}"
            edge = board.get_edge(edge_id)
            if edge and edge.is_occupied:
                text = SYM_EDGE_PLAYER_A if edge.owner == str(player_a_id) else SYM_EDGE_PLAYER_B
                callback = cb_noop("occupied")
            else:
                number = get_number_for_edge(board, edge_id)
                text = str(number) if number else "?"
                callback = cb_edge_h(r*2, c*2+1) # matrix coords: r*2, c*2+1 for horizontal
            
            h_row.append(InlineKeyboardButton(text, callback_data=callback))
            
        # Chunk horizontal row (max 8 per row)
        for i in range(0, len(h_row), 8):
            all_rows.append(h_row[i:i+8])
            
        # Vertical edges (width+1 buttons)
        # Only if not the last row
        if r < board.height:
            v_row = []
            for c in range(board.width + 1):
                edge_id = f"v_{r}_{c}"
                edge = board.get_edge(edge_id)
                if edge and edge.is_occupied:
                    text = SYM_EDGE_PLAYER_A if edge.owner == str(player_a_id) else SYM_EDGE_PLAYER_B
                    callback = cb_noop("occupied")
                else:
                    number = get_number_for_edge(board, edge_id)
                    text = str(number) if number else "?"
                    callback = cb_edge_v(r*2+1, c*2) # matrix coords: r*2+1, c*2 for vertical
                
                v_row.append(InlineKeyboardButton(text, callback_data=callback))
                
            # Chunk vertical row (max 8 per row)
            for i in range(0, len(v_row), 8):
                all_rows.append(v_row[i:i+8])
    
    # 2. Pagination Logic
    MAX_BUTTONS_PER_PAGE = 60 # Safe limit under 100
    pages = []
    current_page_rows = []
    current_page_buttons = 0
    
    for row in all_rows:
        if current_page_buttons + len(row) > MAX_BUTTONS_PER_PAGE:
            pages.append(current_page_rows)
            current_page_rows = []
            current_page_buttons = 0
        
        current_page_rows.append(row)
        current_page_buttons += len(row)
    
    if current_page_rows:
        pages.append(current_page_rows)
        
    # Ensure page index valid
    if not pages:
        return InlineKeyboardMarkup([])
        
    if page >= len(pages):
        page = len(pages) - 1
    if page < 0:
        page = 0
        
    # Set buttons to current page content
    buttons = pages[page]
    
    # 3. Navigation Controls
    nav_row = []
    if len(pages) > 1:
        # Prev button
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=cb_page(page - 1)))
        
        # Page indicator
        nav_row.append(InlineKeyboardButton(f"{page + 1}/{len(pages)}", callback_data=cb_noop("page")))
        
        # Next button
        if page < len(pages) - 1:
            nav_row.append(InlineKeyboardButton("➡️", callback_data=cb_page(page + 1)))
            
        buttons.append(nav_row)
    
    # Leave button
    buttons.append([
        InlineKeyboardButton("🚪 Покинуть игру", callback_data="leave"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def post_game_keyboard(can_rematch: bool = True) -> InlineKeyboardMarkup:
    """Post-game keyboard with rematch and menu options."""
    buttons = []
    
    if can_rematch:
        buttons.append([
            InlineKeyboardButton(BTN_REMATCH, callback_data=cb_rematch()),
            InlineKeyboardButton(BTN_TO_MENU, callback_data=cb_menu("main")),
        ])
        buttons.append([
            InlineKeyboardButton(BTN_WATCH_AD, url="https://otieu.com/4/10513519"),
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


def rematch_confirm_keyboard() -> InlineKeyboardMarkup:
    """Rematch confirmation keyboard for opponent."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да", callback_data="rm:yes"),
            InlineKeyboardButton("❌ Нет", callback_data="rm:no"),
        ],
    ])


def rematch_waiting_keyboard() -> InlineKeyboardMarkup:
    """Waiting for rematch response keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Ожидаем ответ...", callback_data="noop:wait")],
        [InlineKeyboardButton(BTN_TO_MENU, callback_data=cb_menu("main"))],
    ])


def back_keyboard(destination: str = "main") -> InlineKeyboardMarkup:
    """Simple back button keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu(destination))],
    ])
