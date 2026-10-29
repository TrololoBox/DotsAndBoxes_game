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


def main_menu_keyboard(room=None) -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    if room is not None:
        rows = [
            [InlineKeyboardButton("▶️ Продолжить игру", callback_data="menu:resume")],
            [InlineKeyboardButton("🚪 Завершить игру", callback_data="leave:ask")],
            [InlineKeyboardButton("📖 Как играть", callback_data="menu:rules")],
        ]
        return bind_game_keyboard(InlineKeyboardMarkup(rows), room)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Быстрая игра", callback_data="menu:quick")],
        [InlineKeyboardButton("🎮 Другие режимы", callback_data=cb_menu("play"))],
        [InlineKeyboardButton("📖 Как играть", callback_data="menu:rules")],
    ])


def persistent_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom menu keyboard (can be collapsed by user)."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 Меню"), KeyboardButton("▶️ Продолжить")],
        ],
        resize_keyboard=True,
    )


def play_mode_keyboard() -> InlineKeyboardMarkup:
    """Game mode selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_PVE, callback_data=cb_mode("pve"))],
        [InlineKeyboardButton(BTN_PVP_FRIEND, callback_data=cb_mode("pvp_friend"))],
        [InlineKeyboardButton(BTN_PVP_WORLD, callback_data=cb_mode("pvp_world"))],
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("main"))],
    ])


def board_size_keyboard(expanded: bool = False) -> InlineKeyboardMarkup:
    """Board size selection keyboard."""
    rows = [
        [InlineKeyboardButton("3×3 (9 квадратов)", callback_data=cb_size(3))],
        [InlineKeyboardButton("3×4 (12 квадратов)", callback_data=cb_size(10304))],
    ]
    if expanded:
        rows.extend([
            [InlineKeyboardButton("3×5 (15 квадратов)", callback_data=cb_size(10305))],
            [InlineKeyboardButton("4×4 (16 квадратов)", callback_data=cb_size(10404))],
            [InlineKeyboardButton("5×5 — большое поле", callback_data=cb_size(10505))],
            [InlineKeyboardButton("6×6 — большое поле", callback_data=cb_size(10606))],
        ])
    else:
        rows.append([InlineKeyboardButton("📐 Другие размеры", callback_data="menu:sizes_more")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("play"))])
    return InlineKeyboardMarkup(rows)


def difficulty_keyboard() -> InlineKeyboardMarkup:
    """Bot difficulty selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_EASY, callback_data=cb_diff("easy"))],
        [InlineKeyboardButton(BTN_MEDIUM, callback_data=cb_diff("medium"))],
        [InlineKeyboardButton(BTN_HARD, callback_data=cb_diff("hard"))],
        [InlineKeyboardButton(BTN_BACK, callback_data=cb_menu("sizes"))],
    ])


def queue_keyboard() -> InlineKeyboardMarkup:
    """Queue waiting keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Пока сыграть с ботом", callback_data="menu:quick")],
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


NUMBER_COLUMNS = 6
NUMBERS_PER_PAGE = 42


def numbered_edge_keyboard(board: Board, page: int = 0) -> InlineKeyboardMarkup:
    """Fixed number ranges; remove taken moves without renumbering the rest."""
    from game.edge_numbering import get_edge_numbers
    count = lines_page_count(board)
    page = max(0, min(page, count - 1))
    lower, upper = page * NUMBERS_PER_PAGE + 1, min((page + 1) * NUMBERS_PER_PAGE, board.total_edges)
    free = [InlineKeyboardButton(str(number), callback_data=cb_num(number))
            for edge_id, number in get_edge_numbers(board).items()
            if lower <= number <= upper and not board.get_edge(edge_id).is_occupied]
    rows = [free[i:i + NUMBER_COLUMNS] for i in range(0, len(free), NUMBER_COLUMNS)]
    if not rows:
        rows = [[InlineKeyboardButton("Здесь все линии заняты", callback_data="noop:page")]]
    if count > 1:
        nav = []
        if page:
            nav.append(InlineKeyboardButton("◀️", callback_data=cb_page(page - 1)))
        nav.append(InlineKeyboardButton(f"№{lower}–{upper} · {page + 1}/{count}", callback_data="noop:page"))
        if page + 1 < count:
            nav.append(InlineKeyboardButton("▶️", callback_data=cb_page(page + 1)))
        rows.append(nav)
    rows.append([
        InlineKeyboardButton("📋 Меню", callback_data="menu:main"),
        InlineKeyboardButton("🚪 Выйти", callback_data="leave:ask"),
    ])
    return InlineKeyboardMarkup(rows)


def lines_keyboard(board: Board, player_a_id: str, player_b_id: Optional[str] = None, page: int = 0) -> InlineKeyboardMarkup:
    """Compatibility entry point for older callers; same numbered controls."""
    return numbered_edge_keyboard(board, page)


def leave_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🚪 Да, завершить", callback_data="leave:yes"),
        InlineKeyboardButton("▶️ Продолжить", callback_data="leave:no"),
    ]])


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
    # No caller currently schedules AFK; do not advertise unimplemented rules.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("AFK пока недоступен", callback_data="noop:afk")],
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


def bind_game_keyboard(keyboard: InlineKeyboardMarkup, room) -> InlineKeyboardMarkup:
    """Bind every state-changing button to this match and board revision."""
    rows = []
    for row in keyboard.inline_keyboard:
        buttons = []
        for button in row:
            data = button.to_dict()
            callback = data.get("callback_data")
            if callback and (callback.split(":")[0] in {"e", "num", "pg", "afk", "rm", "leave"}):
                data["callback_data"] = f"{callback}:{room.id}:{room.state_version}"
                if len(data["callback_data"].encode()) > 64:
                    raise ValueError("Callback exceeds Telegram limit")
            buttons.append(InlineKeyboardButton(**data))
        rows.append(buttons)
    return InlineKeyboardMarkup(rows)


def lines_page_count(board: Board) -> int:
    """Pages use fixed ranges, independent of occupied edges."""
    return max(1, (board.total_edges + NUMBERS_PER_PAGE - 1) // NUMBERS_PER_PAGE)
