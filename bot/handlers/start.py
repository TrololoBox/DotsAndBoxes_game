"""Welcome, explicit resume and photo-safe menu navigation."""
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from state.cleanup import cleanup_stale_rooms
from state.players import get_or_create_player, get_player
from state.rooms import get_room, RoomState
from telegram_pkg.keyboards import main_menu_keyboard, persistent_menu_keyboard, bind_game_keyboard
from telegram_pkg.messages import RULES_MESSAGE
from telegram_pkg.screens import show_screen
from bot.config import logger


def get_main_menu_keyboard():
    return main_menu_keyboard()


def current_room(user_id):
    player = get_player(user_id)
    room = get_room(player.current_room_id) if player and player.current_room_id else None
    return room if room and user_id in (room.player_a_id, room.player_b_id) else None


async def show_main_menu(update, context):
    cleanup_stale_rooms()
    room = current_room(update.effective_user.id)
    open_room = room if room and room.state in (RoomState.ACTIVE, RoomState.PENDING) else None
    text = "🎯 <b>Точки и квадраты</b>\n\n"
    text += "У тебя есть текущая игра. Продолжить или завершить?" if open_room else "Быстрая игра — поле 3×3 против лёгкого бота."
    await show_screen(update, context, text, main_menu_keyboard(open_room))


async def resume_current_game(update, context):
    room = current_room(update.effective_user.id)
    if not room:
        return False
    user_id = update.effective_user.id
    if room.state == RoomState.PENDING:
        from bot.handlers.play import show_friend_invite
        await show_friend_invite(update, context, room)
        return True
    from bot.handlers.game import send_game_state_new_message, make_bot_move, send_game_over
    async with room.lock:
        if get_room(room.id) is not room or current_room(user_id) is not room:
            return False
        if room.state == RoomState.COMPLETED:
            await send_game_over(update, context, room, only_current_user=True)
        elif room.state == RoomState.ACTIVE:
            if room.is_pve() and room.current_player_index == 1:
                await make_bot_move(update, context, room)
            else:
                await send_game_state_new_message(update, context, room, user_id)
        else:
            return False
    return True


async def start_command(update, context):
    user = update.effective_user
    cleanup_stale_rooms()
    get_or_create_player(user.id, user.username, user.first_name)
    args = context.args or []
    if args and (code := _parse_invite_code(args[0])):
        await handle_invite_join(update, context, code)
        return
    if await resume_current_game(update, context):
        return
    welcome = (
        f"👋 Привет, {escape(user.first_name)}!\n\n"
        "🎯 <b>Точки и квадраты</b>\n"
        "Нажимай номера линий и замыкай квадраты.\n"
        "За каждый квадрат — очко и ещё один ход.\n\n"
        "Начни с короткой игры 3×3 против лёгкого бота."
    )
    await update.message.reply_text(welcome, parse_mode="HTML", reply_markup=main_menu_keyboard())
    await update.message.reply_text(
        "📋 Меню — выбрать действие. ▶️ Продолжить — вернуться к партии.",
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
    
    from state.cleanup import cleanup_stale_rooms
    from bot.handlers.play import has_open_room
    from state.players import get_player
    cleanup_stale_rooms()
    owner = get_player(room.player_a_id)
    if get_room_by_invite(invite_code) is not room or not owner or owner.current_room_id != room.id:
        await update.message.reply_text("Приглашение истекло")
        return
    if has_open_room(user.id):
        await update.message.reply_text("Сначала завершите текущую игру через /start")
        return
    from state.queues import leave_queue
    leave_queue(user.id)
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


async def main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    action = query.data.removeprefix("menu:")
    if action == "quick":
        from bot.handlers.play import start_quick_game
        await start_quick_game(update, context)
    elif action == "resume":
        if not await resume_current_game(update, context):
            await show_main_menu(update, context)
    elif action == "rules":
        room = current_room(update.effective_user.id)
        back = "menu:resume" if room and room.state == RoomState.ACTIVE else "menu:main"
        await show_screen(update, context, RULES_MESSAGE, InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Вернуться", callback_data=back)],
        ]))
    elif action == "play":
        from telegram_pkg.keyboards import play_mode_keyboard
        await show_screen(update, context, "🎮 <b>С кем играем?</b>", play_mode_keyboard())
    elif action in ("sizes", "sizes_more"):
        from telegram_pkg.keyboards import board_size_keyboard
        await show_screen(update, context, "📐 <b>Размер поля</b>", board_size_keyboard(action == "sizes_more"))
    else:
        # Legacy profile/settings/support buttons return to working actions.
        await show_main_menu(update, context)
