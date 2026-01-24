"""
Start command and main menu handler.

Handles /start and main menu navigation.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import logger
from telegram_pkg.messages import (
    WELCOME_MESSAGE,
    MAIN_MENU_TITLE,
    PROFILE_TEMPLATE,
    SETTINGS_TEMPLATE,
    SUPPORT_MESSAGE,
    INVITE_NOT_FOUND,
    INVITE_ALREADY_STARTED,
    INVITE_SELF_JOIN,
    BTN_BACK,
    USERNAME_NOT_SET,
    THEME_CLASSIC_NAME,
)
from telegram_pkg.keyboards import main_menu_keyboard


# Main menu keyboard layout
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    # Check for invite code in deep link
    args = context.args
    if args:
        invite_arg = args[0]
        invite_code = _parse_invite_code(invite_arg)
        if invite_code:
            logger.info(f"User {user.id} joining with invite code: {invite_code}")
            await handle_invite_join(update, context, invite_code)
            return
    
    # Show main menu
    await update.message.reply_text(
        WELCOME_MESSAGE.format(name=user.first_name),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def handle_invite_join(update: Update, context: ContextTypes.DEFAULT_TYPE, invite_code: str) -> None:
    """Handle player joining via invite link."""
    from state.rooms import get_room_by_invite, RoomState
    from state.players import get_or_create_player, set_player_room
    from state.engine import start_game
    
    user = update.effective_user
    
    # Find the room by invite code
    room = get_room_by_invite(invite_code)
    
    if not room:
        await update.message.reply_text(
            INVITE_NOT_FOUND,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return
    
    if room.state != RoomState.WAITING:
        await update.message.reply_text(
            INVITE_ALREADY_STARTED,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return
    
    # Check if user is trying to join their own game
    if room.player_a_id == user.id:
        await update.message.reply_text(
            INVITE_SELF_JOIN,
            parse_mode="Markdown",
        )
        return
    
    # Add player B to the room
    player_b = get_or_create_player(user.id, user.username, user.first_name)
    room.player_b_id = user.id
    room.player_b_emoji = player_b.emoji
    
    set_player_room(user.id, room.id)
    
    # Start the game
    result = start_game(room)
    if not result.ok:
        await update.message.reply_text(
            INVITE_ALREADY_STARTED,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return
    
    logger.info(f"Player {user.id} joined room {room.id} via invite. Game started!")
    
    # Send game state to joining player
    from bot.handlers.game import send_game_state_new_message
    await send_game_state_new_message(update, context, room, user.id)
    
    await send_game_state_new_message(update, context, room, room.player_a_id)


def _parse_invite_code(invite_arg: str) -> str | None:
    """Parse invite code from a /start deep link argument."""
    if not invite_arg:
        return None
    normalized = invite_arg.strip()
    if normalized.startswith("invite_"):
        return normalized.replace("invite_", "", 1)
    if normalized.startswith("invite-"):
        return normalized.replace("invite-", "", 1)
    if normalized.startswith("invite"):
        return normalized.replace("invite", "", 1).lstrip("_-")
    return None


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu button clicks."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    action = query.data.replace("menu:", "")
    logger.info(f"User {user.id} selected menu:{action}")
    
    if action == "main":
        # Return to main menu
        await query.edit_message_text(
            MAIN_MENU_TITLE,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    
    elif action == "play":
        # Show play mode selection
        from telegram_pkg.keyboards import play_mode_keyboard
        from telegram_pkg.messages import PLAY_MODE_TITLE
        
        await query.edit_message_text(
            PLAY_MODE_TITLE,
            parse_mode="Markdown",
            reply_markup=play_mode_keyboard(),
        )
    
    elif action == "profile":
        # TODO: Show profile
        await query.edit_message_text(
            PROFILE_TEMPLATE.format(
                name=user.first_name,
                username=f"@{user.username}" if user.username else USERNAME_NOT_SET,
                emoji="😀",
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(BTN_BACK, callback_data="menu:main")]
            ]),
        )
    
    elif action == "settings":
        # TODO: Show settings
        await query.edit_message_text(
            SETTINGS_TEMPLATE.format(theme=THEME_CLASSIC_NAME),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(BTN_BACK, callback_data="menu:main")]
            ]),
        )
    
    elif action == "support":
        # TODO: Show support/donation
        await query.edit_message_text(
            SUPPORT_MESSAGE,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(BTN_BACK, callback_data="menu:main")]
            ]),
        )
