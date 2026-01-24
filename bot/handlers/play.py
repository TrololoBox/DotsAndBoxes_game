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
from state.players import get_or_create_player, set_player_room
from state.rooms import create_room, GameMode
from state.queues import join_queue, leave_queue, find_match, get_queue_position


logger = logging.getLogger(__name__)


# Store pending selections in context
PENDING_MODE_KEY = "pending_mode"
PENDING_SIZE_KEY = "pending_size"


async def play_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle play-related callbacks."""
    query = update.callback_query
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
    
    await query.edit_message_text(
        PLAY_MODE_TITLE,
        parse_mode="Markdown",
        reply_markup=play_mode_keyboard(),
    )


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
    await query.edit_message_text(
        PLAY_SIZE_TITLE,
        parse_mode="Markdown",
        reply_markup=board_size_keyboard(),
    )


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
    
    if mode == "pve":
        # Show difficulty selection for PvE
        await query.edit_message_text(
            PLAY_DIFFICULTY_TITLE,
            parse_mode="Markdown",
            reply_markup=difficulty_keyboard(),
        )
    
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
                await query.edit_message_text(
                    QUEUE_WAITING.format(size=size, position=position),
                    parse_mode="Markdown",
                    reply_markup=queue_keyboard(),
                )
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
    
    # Import here to avoid circular import
    from bot.handlers.game import send_game_state
    await send_game_state(update, context, room)


async def handle_cancel_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle queue cancellation."""
    query = update.callback_query
    user = update.effective_user
    
    if leave_queue(user.id):
        await query.edit_message_text(
            "❌ Поиск отменён.\n\nВозвращаемся в меню...",
        )
        
        # Return to mode selection
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
    
    player_a = get_player(player_a_id)
    player_b = get_player(player_b_id)
    
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
    
    # Notify both players
    # Note: In production, we'd need to send messages to both users
    from bot.handlers.game import send_game_state
    await send_game_state(update, context, room)


async def create_friend_invite(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    size: int,
) -> None:
    """Create a friend invite room."""
    query = update.callback_query
    user = update.effective_user
    
    player = get_or_create_player(user.id, user.username, user.first_name)
    
    room = create_room(
        mode=GameMode.PVP_FRIEND,
        board_size=size,
        player_a_id=user.id,
        player_a_emoji=player.emoji,
    )
    
    set_player_room(user.id, room.id)
    
    # Generate invite link
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=invite_{room.invite_code}"
    
    from telegram_pkg.messages import INVITE_CREATED
    await query.edit_message_text(
        INVITE_CREATED.format(link=invite_link, code=room.invite_code),
        parse_mode="Markdown",
    )
