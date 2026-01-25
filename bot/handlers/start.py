"""
Start command and main menu handler.

Handles /start and main menu navigation.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import logger


# Main menu keyboard layout
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Generate the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("🎮 Играть", callback_data="menu:play")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings"),
        ],
        [InlineKeyboardButton("💝 Поддержать проект", callback_data="menu:support")],
    ]
    return InlineKeyboardMarkup(keyboard)


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
    
    # Import persistent keyboard
    from telegram_pkg.keyboards import persistent_menu_keyboard
    
    # Show main menu with persistent reply keyboard
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🎯 *Точки и Квадраты* — классическая игра на бумаге, "
        "теперь в Telegram!\n\n"
        "Соедини точки линиями и захвати больше квадратов, "
        "чем противник.\n\n"
        "Выбери действие:"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )
    
    # Send persistent bottom keyboard separately (it persists)
    await update.message.reply_text(
        "💡 Кнопка «Меню» всегда доступна внизу.",
        reply_markup=persistent_menu_keyboard(),
    )


async def handle_invite_join(update: Update, context: ContextTypes.DEFAULT_TYPE, invite_code: str) -> None:
    """Handle player joining via invite link."""
    from state.rooms import get_room_by_invite, RoomState
    from state.players import get_or_create_player, set_player_room
    
    user = update.effective_user
    
    # Find the room by invite code
    room = get_room_by_invite(invite_code)
    
    if not room:
        await update.message.reply_text(
            "❌ *Приглашение не найдено*\n\n"
            "Возможно, оно истекло или уже использовано.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    if room.state != RoomState.PENDING:
        await update.message.reply_text(
            "❌ *Игра уже началась*\n\n"
            "Это приглашение уже было использовано.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )
        return
    
    # Check if user is trying to join their own game
    if room.player_a_id == user.id:
        await update.message.reply_text(
            "🤔 *Это ваше приглашение!*\n\n"
            "Отправьте ссылку другу, чтобы он присоединился.",
            parse_mode="Markdown",
        )
        return
    
    # Add player B to the room
    player_b = get_or_create_player(user.id, user.username, user.first_name)
    room.player_b_id = user.id
    room.player_b_emoji = player_b.emoji
    
    set_player_room(user.id, room.id)
    
    # Start the game
    room.start_game()
    
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
        text = (
            "🎯 *Точки и Квадраты*\n\n"
            "Выбери действие:"
        )
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
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
            "👤 *Профиль*\n\n"
            f"Имя: {user.first_name}\n"
            f"Username: @{user.username or 'не указан'}\n"
            "Эмодзи: 😀\n\n"
            "🚧 Раздел в разработке",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="menu:main")]
            ]),
        )
    
    elif action == "settings":
        # TODO: Show settings
        await query.edit_message_text(
            "⚙️ *Настройки*\n\n"
            "Тема: Классика\n\n"
            "🚧 Раздел в разработке",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="menu:main")]
            ]),
        )
    
    elif action == "support":
        # TODO: Show support/donation
        await query.edit_message_text(
            "💝 *Поддержать проект*\n\n"
            "Спасибо за интерес к игре!\n"
            "Способы поддержки появятся позже.\n\n"
            "🚧 Раздел в разработке",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="menu:main")]
            ]),
        )
