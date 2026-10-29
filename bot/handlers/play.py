"""
Play handler for game mode, size, and difficulty selection.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from telegram_pkg.callback_parser import parse_callback, CallbackAction
from telegram_pkg.keyboards import (
    play_mode_keyboard, board_size_keyboard, difficulty_keyboard, queue_keyboard
)
from telegram_pkg.messages import (
    PLAY_MODE_TITLE, PLAY_SIZE_TITLE, PLAY_DIFFICULTY_TITLE, QUEUE_WAITING
)
from state.players import get_or_create_player, set_player_room, get_player
from state.rooms import create_room, GameMode, get_room, RoomState
from state.queues import join_queue, leave_queue, find_match, get_queue_position
from telegram_pkg.screens import show_screen


logger = logging.getLogger(__name__)


# Store pending selections in context
PENDING_MODE_KEY = "pending_mode"
PENDING_SIZE_KEY = "pending_size"


async def play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle play-related callbacks."""
    query = update.callback_query
    from state.cleanup import cleanup_stale_rooms
    cleanup_stale_rooms()
    await query.answer()
    
    user = update.effective_user
    callback = parse_callback(query.data)
    
    logger.info(f"User {user.id} play callback: {query.data}")
    
    if callback.action == CallbackAction.MODE:
        await handle_mode_selection(update, context, callback.param1)
    
    elif callback.action == CallbackAction.SIZE:
        await handle_size_selection(update, context, int(callback.param1))
    
    elif callback.action == CallbackAction.DIFF:
        await handle_difficulty_selection(update, context, callback.param1)
    
    elif callback.action == CallbackAction.CANCEL_QUEUE:
        await handle_cancel_queue(update, context)


async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show game mode selection screen."""
    query = update.callback_query
    
    await show_screen(update, context, PLAY_MODE_TITLE, play_mode_keyboard(), "Markdown")


async def handle_mode_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode: str,
) -> None:
    """Handle game mode selection."""
    query = update.callback_query
    
    # Store selected mode
    context.user_data[PENDING_MODE_KEY] = mode
    
    # Show size selection
    await show_screen(update, context, PLAY_SIZE_TITLE, board_size_keyboard(), "Markdown")


async def handle_size_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    size: int,
) -> None:
    """Handle board size selection."""
    query = update.callback_query
    user = update.effective_user
    
    mode = context.user_data.get(PENDING_MODE_KEY, "pve")
    context.user_data[PENDING_SIZE_KEY] = size
    
    get_or_create_player(user.id, user.username, user.first_name)
    if has_open_room(user.id):
        from bot.handlers.start import show_main_menu
        await show_main_menu(update, context)
        return
    if mode != "pvp_world":
        leave_queue(user.id)
    if mode == "pve":
        # Show difficulty selection for PvE
        await show_screen(update, context, PLAY_DIFFICULTY_TITLE, difficulty_keyboard(), "Markdown")
    
    elif mode == "pvp_world":
        # Join matchmaking queue
        if join_queue(user.id, size):
            position = get_queue_position(user.id)
            
            # Try to find match immediately
            match = find_match(size)
            if match:
                # Match found - create room
                player_a, player_b = match
                await start_pvp_game(update, context, player_a, player_b, size)
            else:
                # Wait in queue
                width = (size - 10000) // 100 if size > 100 else size
                height = size % 100 if size > 100 else size
                text = QUEUE_WAITING.format(size=width, position=position).replace(f"{width}×{width}", f"{width}×{height}")
                await show_screen(update, context, text, queue_keyboard(), "Markdown")
        else:
            await query.answer("Вы уже в очереди!", show_alert=True)
    
    elif mode == "pvp_friend":
        # Create invite room
        await create_friend_invite(update, context, size)


async def handle_difficulty_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    difficulty: str,
) -> None:
    """Handle PvE difficulty selection and start game."""
    query = update.callback_query
    user = update.effective_user
    
    size = context.user_data.get(PENDING_SIZE_KEY, 3)
    
    # Get or create player profile
    player = get_or_create_player(user.id, user.username, user.first_name)
    
    if has_open_room(user.id):
        from bot.handlers.start import show_main_menu
        await show_main_menu(update, context)
        return
    leave_queue(user.id)
    # Create PvE room
    room = create_room(
        mode=GameMode.PVE,
        board_size=size,
        player_a_id=user.id,
        bot_difficulty=difficulty,
        player_a_emoji=player.emoji,
        player_b_emoji="🤖",
        theme=player.theme,
    )
    
    # Update player's current room
    set_player_room(user.id, room.id)
    
    # Start the game
    room.start_game()
    logger.info(f"Room {room.id} started. Sending initial state.")
    
    # Import here to avoid circular import
    from bot.handlers.game import send_game_state
    try:
        await send_game_state(update, context, room)
        logger.info("Initial state sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send game state: {e}", exc_info=True)
        if query:
            await query.answer("Не удалось показать поле. Нажми /start, чтобы продолжить.", show_alert=True)
        else:
            await update.message.reply_text("Не удалось показать поле. Нажми /start, чтобы продолжить.")


async def start_quick_game(update, context) -> None:
    """One tap to the same real PvE pipeline; never replace an open match."""
    context.user_data[PENDING_MODE_KEY] = "pve"
    context.user_data[PENDING_SIZE_KEY] = 3
    await handle_difficulty_selection(update, context, "easy")


async def handle_cancel_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle queue cancellation."""
    query = update.callback_query
    user = update.effective_user
    
    if leave_queue(user.id):
        await show_mode_selection(update, context)
    else:
        await query.answer("Вы не в очереди.", show_alert=True)


async def start_pvp_game(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    player_a_id: int,
    player_b_id: int,
    size: int,
) -> None:
    """Start a PvP game between two matched players."""
    from state.players import get_player
    
    if has_open_room(player_a_id) or has_open_room(player_b_id) or player_a_id == player_b_id:
        await update.callback_query.answer("Игрок уже занят")
        return
    player_a = get_or_create_player(player_a_id, "", "Игрок")
    player_b = get_or_create_player(player_b_id, "", "Игрок")
    
    room = create_room(
        mode=GameMode.PVP_WORLD,
        board_size=size,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        player_a_emoji=player_a.emoji if player_a else "😀",
        player_b_emoji=player_b.emoji if player_b else "😎",
    )
    
    set_player_room(player_a_id, room.id)
    set_player_room(player_b_id, room.id)
    
    room.start_game()
    
    from bot.handlers.game import send_game_state_new_message
    await send_game_state_new_message(update, context, room, player_a_id)
    await send_game_state_new_message(update, context, room, player_b_id)


async def create_friend_invite(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    size: int,
) -> None:
    """Create a friend invite room."""
    query = update.callback_query
    user = update.effective_user
    
    player = get_or_create_player(user.id, user.username, user.first_name)

    if has_open_room(user.id):
        from bot.handlers.start import show_main_menu
        await show_main_menu(update, context)
        return
    
    room = create_room(
        mode=GameMode.PVP_FRIEND,
        board_size=size,
        player_a_id=user.id,
        player_a_emoji=player.emoji,
    )
    
    set_player_room(user.id, room.id)
    await show_friend_invite(update, context, room)


async def show_friend_invite(update, context, room):
    """Recover the same invitation, including its link, from any menu screen."""
    # Generate invite link
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=invite_{room.invite_code}"
    
    from html import escape
    from telegram_pkg.keyboards import bind_game_keyboard
    
    invite_message = (
        "👥 <b>Приглашение создано!</b>\n\n"
        f"Нажми кнопку ниже, чтобы пригласить друга, или отправь ссылку:\n"
        f"<code>{escape(invite_link)}</code>\n\n"
        "⏳ Ссылка действительна 10 минут."
    )
    
    # Telegram's share URL works without an inline-query handler or /setinline.
    from urllib.parse import urlencode
    share_url = "https://t.me/share/url?" + urlencode({
        "url": invite_link, "text": "🎮 Давай сыграем в Точки и Квадраты!",
    })
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Отправить другу", url=share_url)],
        [InlineKeyboardButton("❌ Отменить", callback_data="leave")],
    ])
    
    await show_screen(update, context, invite_message, bind_game_keyboard(keyboard, room))


def has_open_room(user_id: int) -> bool:
    player = get_player(user_id)
    room = get_room(player.current_room_id) if player and player.current_room_id else None
    return room is not None and room.state in {RoomState.PENDING, RoomState.ACTIVE}
