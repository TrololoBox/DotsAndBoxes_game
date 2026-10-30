"""
Game handler for in-game interactions.

Handles edge placement, turn management, and game state updates.
All invalid taps receive toast feedback (no silent failures).
"""

import logging
import io
from telegram import Update, InputFile
from telegram.error import TelegramError, BadRequest
from telegram.ext import ContextTypes

from telegram_pkg.callback_parser import parse_callback, CallbackAction, matrix_to_edge_id
from telegram_pkg.keyboards import (
    game_board_keyboard, numbered_edge_keyboard, lines_keyboard,
    post_game_keyboard, bind_game_keyboard, lines_page_count
)
from telegram_pkg.messages import (
    GAME_STATUS, YOUR_TURN, OPPONENT_TURN, BOT_TURN,
    CAPTURE_SINGLE, CAPTURE_DOUBLE, GAME_OVER_WIN, GAME_OVER_LOSE, GAME_OVER_DRAW,
    NUMBERED_MODE_HELP
)
from telegram_pkg.toasts import (
    toast_occupied_edge, toast_tap_dot, toast_tap_square,
    toast_not_your_turn, toast_game_finished, toast_transition_state
)
from state.rooms import Room, get_room, RoomState, delete_room
from state.players import get_player, set_player_room
from game.turn import TurnError
from game.scoring import calculate_result
from render.board_renderer import render_board
from ai.easy import EasyBot
from ai.medium import MediumBot
from ai.hard import HardBot


logger = logging.getLogger(__name__)


# Bot instances
BOTS = {
    "easy": EasyBot(),
    "medium": MediumBot(),
    "hard": HardBot(),
}


async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Validate match identity/revision under the room lock before any mutation."""
    query = update.callback_query
    user = update.effective_user
    callback = parse_callback(query.data)
    if callback.is_noop:
        await handle_noop(update, context, callback.noop_reason)
        return
    from state.cleanup import cleanup_stale_rooms
    cleanup_stale_rooms()
    player = get_player(user.id)
    room = get_room(callback.room_id) if callback.room_id else None
    if not room or not player:
        await query.answer("Кнопка устарела. Откройте текущую игру через /start.")
        return
    async with room.lock:
        if (get_room(room.id) is not room or player.current_room_id != room.id
                or user.id not in (room.player_a_id, room.player_b_id)):
            await query.answer("Кнопка устарела. Используйте текущее поле.")
            return
        if callback.version != room.state_version:
            # Do not replay the requested action. Refresh this player's current view.
            try:
                await query.answer("Поле обновилось. Показываю текущее состояние.")
            except TelegramError:
                logger.warning("Could not acknowledge board refresh")
            if room.state == RoomState.ACTIVE:
                await send_game_state(update, context, room)
            elif room.state == RoomState.COMPLETED:
                await send_game_over(update, context, room, only_current_user=True)
            elif room.state == RoomState.PENDING:
                from bot.handlers.play import show_friend_invite
                await show_friend_invite(update, context, room)
            return
        if callback.action == CallbackAction.REMATCH:
            if room.state != RoomState.COMPLETED:
                await query.answer(toast_transition_state())
                return
            if callback.param1 in ("yes", "no"):
                await handle_rematch_response(update, context, callback.param1)
            else:
                await handle_rematch(update, context)
        elif callback.action == CallbackAction.LEAVE:
            await query.answer()
            if callback.param1 == "ask":
                from telegram_pkg.keyboards import leave_confirm_keyboard
                from telegram_pkg.screens import show_screen
                await show_screen(update, context,
                    "🚪 <b>Завершить эту игру?</b>\nВернуться к этой партии после выхода не получится.",
                    bind_game_keyboard(leave_confirm_keyboard(), room))
            elif callback.param1 == "no":
                if room.state == RoomState.ACTIVE:
                    await send_game_state(update, context, room)
                else:
                    from bot.handlers.play import show_friend_invite
                    await show_friend_invite(update, context, room)
            else:
                await handle_leave_game(update, context)
        elif room.state != RoomState.ACTIVE:
            await query.answer(toast_game_finished())
        elif callback.action == CallbackAction.EDGE:
            await handle_edge_placement(update, context, callback)
        elif callback.is_num:
            await handle_numbered_edge_placement(update, context, room, callback)
        elif callback.action == CallbackAction.PAGE:
            try:
                page = int(callback.param1)
            except (TypeError, ValueError):
                page = -1
            if room.input_mode not in {"numbered", "lines"} or not 0 <= page < lines_page_count(room.board):
                await query.answer("Неверная страница")
                return
            room.current_page = page
            room.pages_by_player[user.id] = page
            await query.answer()
            await send_game_state(update, context, room)
        elif callback.action == CallbackAction.AFK:
            await handle_afk_choice(update, context, callback.param1)
        else:
            await query.answer()


async def handle_noop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reason: str,
) -> None:
    """Handle noop callbacks with appropriate toast feedback."""
    query = update.callback_query
    
    if reason == "dot":
        await query.answer(toast_tap_dot(), show_alert=False)
    
    elif reason == "square":
        await query.answer(toast_tap_square(), show_alert=False)
    
    elif reason == "occupied":
        await query.answer(toast_occupied_edge(), show_alert=False)
    
    elif reason == "ad":
        await query.answer("📺 Рекламный блок скоро появится!", show_alert=False)
    
    else:
        await query.answer()


async def handle_edge_placement(update: Update, context, callback) -> None:
    """Translate validated matrix coordinates to a board edge."""
    player = get_player(update.effective_user.id)
    room = get_room(player.current_room_id)
    try:
        edge_id = matrix_to_edge_id(callback.edge_type, callback.edge_matrix_row, callback.edge_matrix_col)
    except (TypeError, ValueError):
        await update.callback_query.answer("Неверная грань")
        return
    await _apply_player_move(update, context, room, edge_id)


async def handle_numbered_edge_placement(update: Update, context, room: Room, callback) -> None:
    """Resolve the stable server-side numbering, never client-supplied indices."""
    from game.edge_numbering import get_edge_by_number
    edge_id = get_edge_by_number(room.board, callback.edge_number)
    await _apply_player_move(update, context, room, edge_id)


async def _apply_player_move(update: Update, context, room: Room, edge_id) -> None:
    query, user = update.callback_query, update.effective_user
    if not room.is_player_turn(user.id):
        await query.answer(toast_not_your_turn())
        return
    result = room.apply_move(str(user.id), edge_id)
    if not result or not result.success:
        message = toast_occupied_edge() if result and result.error == TurnError.EDGE_OCCUPIED else "Неверная грань"
        await query.answer(message)
        return
    # State, revision, next player and completion are committed before this await.
    try:
        await query.answer()
    except TelegramError:
        # An expired query must not interrupt the already-committed turn.
        logger.warning("Could not acknowledge committed move")
    if result.game_over:
        await send_game_over(update, context, room)
    elif room.is_pve() and room.current_player_index == 1:
        await make_bot_move(update, context, room)
    else:
        recipients = [user.id]
        if not room.is_pve() and room.player_b_id:
            other = room.player_b_id if user.id == room.player_a_id else room.player_a_id
            recipients.append(other)
        await send_game_states(update, context, room, recipients)


async def make_bot_move(update: Update, context, room: Room) -> None:
    """Run only the PvE bot's actual turn, including capture chains."""
    bot = BOTS.get(room.bot_difficulty, BOTS["medium"])
    while room.is_pve() and room.state == RoomState.ACTIVE and room.current_player_index == 1:
        edge_id = bot.choose_edge(room.board)
        result = room.apply_move("bot", edge_id) if edge_id else None
        if not result or not result.success:
            logger.error("Bot could not choose a legal move")
            break
        if result.game_over:
            await send_game_over(update, context, room)
            return
    await send_game_state(update, context, room)


def _move_summary(room, user_id):
    """Explain the final move and an opponent's whole capture chain."""
    from game.edge_numbering import get_number_for_edge
    if not room.last_move_edge_id:
        return ""
    yours = room.last_move_player_id == str(user_id)
    actor = "Ты" if yours else "Бот" if room.is_pve() else "Соперник"
    number = get_number_for_edge(room.board, room.last_move_edge_id)
    lines = [f"★ <b>{actor} — №{number}</b>"]
    own_moves = room.last_turns.get(str(user_id), [])
    if not yours and own_moves:
        lines.append(f"Твоя последняя линия: №{get_number_for_edge(room.board, own_moves[-1])}.")
    if len(room.recent_edge_ids) > 1:
        numbers = [str(get_number_for_edge(room.board, edge)) for edge in room.recent_edge_ids]
        shown = ", ".join(numbers[-6:])
        prefix = f"… ещё {len(numbers) - 6}, " if len(numbers) > 6 else ""
        lines.append(f"Серия ходов: №{prefix}{shown}.")
    if room.recent_captures:
        lines.append(f"{actor}: +{room.recent_captures} очк. за квадраты.")
        if room.state == RoomState.ACTIVE and room.last_move_player_id == str(room.current_player_id):
            lines.append("✨ Квадрат замкнут — ходи ещё!" if yours else "✨ За квадрат соперник ходит ещё.")
    return "\n".join(lines)


def game_caption(room, user_id):
    from html import escape
    from game.capture import count_player_squares
    player_a = str(room.player_a_id)
    player_b = str(room.player_b_id) if room.player_b_id else "bot"
    other_id = player_b if str(user_id) == player_a else player_a
    other = get_player(int(other_id)) if other_id != "bot" else None
    difficulty = {"easy": "лёгкий", "medium": "средний", "hard": "сложный"}
    opponent = f"Бот · {difficulty.get(room.bot_difficulty, 'средний')}" if room.is_pve() else (other.display_name if other else "Соперник")
    colours = {"classic": ("🟦", "🟥"), "forest": ("🟩", "🟧"), "night": ("🔵", "🟣")}
    colour_a, colour_b = colours.get(room.theme, colours["classic"])
    your_colour, other_colour = (colour_a, colour_b) if str(user_id) == player_a else (colour_b, colour_a)
    intro = not room.last_move_edge_id
    # Long instructions belong to the rules screen and the initial board.
    status = "🟢 <b>Твой ход</b>" if room.is_player_turn(user_id) else "🤖 <b>Бот думает…</b>" if room.is_pve() else "🔴 <b>Ход соперника</b>"
    caption = (
        f"🎯 <b>{room.board_width}×{room.board_height}</b> · {status}\n"
        f"Ты {your_colour} <b>{count_player_squares(room.board, str(user_id))}</b> : "
        f"<b>{count_player_squares(room.board, other_id)}</b> {other_colour} {escape(opponent)}"
    )
    if intro:
        caption += (f"\n\n{NUMBERED_MODE_HELP}\n"
                    "Квадрат = 1 очко и ещё ход. ★ Золото — последний ход. ✓ — занято.")
    else:
        caption += "\n" + _move_summary(room, user_id)
    return caption


def _board_picture(room):
    return render_board(
        board=room.board, theme_name=room.theme,
        player_a_id=str(room.player_a_id),
        player_b_id=str(room.player_b_id) if room.player_b_id else "bot",
        player_emojis={str(room.player_a_id): room.player_a_emoji,
                       str(room.player_b_id) if room.player_b_id else "bot": room.player_b_emoji},
        show_numbers=True, last_edge_id=room.last_move_edge_id,
        recent_edge_ids=room.recent_edge_ids,
    )


async def _deliver_board(context, room, user_id, image_bytes, caption, keyboard):
    """Edit one game message; replace only if Telegram says it no longer exists."""
    from telegram import InputMediaPhoto
    existing = room.get_message_id(user_id)
    if existing:
        try:
            await context.bot.edit_message_media(
                chat_id=user_id, message_id=existing,
                media=InputMediaPhoto(media=io.BytesIO(image_bytes), caption=caption, parse_mode="HTML"),
                reply_markup=bind_game_keyboard(keyboard, room),
            )
            return
        except BadRequest as exc:
            reason = str(exc).lower()
            if "message is not modified" in reason:
                return
            if "message to edit not found" not in reason and "message can't be edited" not in reason:
                raise
    sent = await context.bot.send_photo(
        chat_id=user_id, photo=io.BytesIO(image_bytes), caption=caption,
        parse_mode="HTML", reply_markup=bind_game_keyboard(keyboard, room),
    )
    room.set_message_id(user_id, sent.message_id)


async def send_game_state(update, context, room):
    await send_game_state_new_message(update, context, room, update.effective_user.id)


async def send_game_state_new_message(update, context, room, user_id):
    from telegram_pkg.keyboards import NUMBERS_PER_PAGE
    from game.edge_numbering import get_free_numbers
    page = room.pages_by_player.get(user_id, 0)
    free = get_free_numbers(room.board)
    if free and not any(page * NUMBERS_PER_PAGE < n <= (page + 1) * NUMBERS_PER_PAGE for n in free):
        page = (free[0] - 1) // NUMBERS_PER_PAGE
        room.pages_by_player[user_id] = page
    await _deliver_board(context, room, user_id, _board_picture(room), game_caption(room, user_id),
                         numbered_edge_keyboard(room.board, page))


async def _deliver_independently(user_ids, deliver):
    """Attempt every recipient even if one Telegram delivery fails."""
    first_error = None
    for user_id in dict.fromkeys(user_ids):
        try:
            await deliver(user_id)
        except TelegramError as exc:
            logger.warning("Board delivery failed for player %s: %s", user_id, type(exc).__name__)
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error


async def send_game_states(update, context, room, user_ids):
    async def deliver(user_id):
        await send_game_state_new_message(update, context, room, user_id)
    await _deliver_independently(user_ids, deliver)


async def send_game_over(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
    only_current_user: bool = False,
) -> None:
    """Send game over message to all players."""
    query = update.callback_query
    user = update.effective_user
    
    player_a_str = str(room.player_a_id)
    player_b_str = str(room.player_b_id) if room.player_b_id else "bot"
    
    # Calculate result
    result = calculate_result(
        board=room.board,
        player_a_id=player_a_str,
        player_b_id=player_b_str,
    )
    
    image_bytes = _board_picture(room)

    recipients = [user.id]
    if not only_current_user and not room.is_pve() and room.player_b_id:
        other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
        recipients.append(other_player_id)
    async def deliver(user_id):
        await _send_game_over_to_player(context, room, result, user_id, image_bytes)
    await _deliver_independently(recipients, deliver)


async def _send_game_over_to_player(
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
    result,
    user_id: int,
    image_bytes: bytes,
) -> None:
    """Send game over message to a specific player."""
    player_a_str = str(room.player_a_id)
    player_b_str = str(room.player_b_id) if room.player_b_id else "bot"
    
    user_is_player_a = user_id == room.player_a_id
    
    if result.is_draw:
        message = GAME_OVER_DRAW.format(score=result.player_a_score)
    elif (result.winner_id == player_a_str and user_is_player_a) or \
         (result.winner_id == player_b_str and not user_is_player_a):
        if user_is_player_a:
            your_score = result.player_a_score
            opponent_score = result.player_b_score
        else:
            your_score = result.player_b_score
            opponent_score = result.player_a_score
        message = GAME_OVER_WIN.format(your_score=your_score, opponent_score=opponent_score)
    else:
        if user_is_player_a:
            your_score = result.player_a_score
            opponent_score = result.player_b_score
        else:
            your_score = result.player_b_score
            opponent_score = result.player_a_score
        message = GAME_OVER_LOSE.format(your_score=your_score, opponent_score=opponent_score)
    
    message += "\n\n" + _move_summary(room, user_id)
    await _deliver_board(context, room, user_id, image_bytes, message, post_game_keyboard(can_rematch=True))


async def handle_rematch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rematch request."""
    query = update.callback_query
    user = update.effective_user
    
    from telegram_pkg.keyboards import main_menu_keyboard, rematch_confirm_keyboard, rematch_waiting_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
    # Get player's current room
    player = get_player(user.id)
    if not player or not player.current_room_id:
        # No active room, just show menu
        try:
            await query.edit_message_caption(
                caption=MAIN_MENU_TITLE,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user.id,
                text=MAIN_MENU_TITLE,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        return
    
    room = get_room(player.current_room_id)
    if not room:
        await query.answer("Игра не найдена")
        return
    
    # PvE: Just start a new game immediately
    if room.is_pve():
        # Create new room with same settings
        from state.rooms import create_room
        new_room = create_room(
            mode=room.mode,
            board_size=room.board_size,
            player_a_id=user.id,
            player_b_id=None,  # Bot
            bot_difficulty=room.bot_difficulty,
            player_a_emoji=room.player_a_emoji,
            player_b_emoji="🤖",
            theme=room.theme,
        )
        new_room.start_game()
        set_player_room(user.id, new_room.id)
        delete_room(room.id)
        
        await query.answer("Начинаем новую игру!")
        await send_game_state_new_message(update, context, new_room, user.id)
        return
    
    opponent_id = room.player_b_id if user.id == room.player_a_id else room.player_a_id
    opponent = get_player(opponent_id)
    if not opponent or opponent.current_room_id != room.id:
        await query.answer("Соперник уже покинул этот матч")
        return

    # PvP: Check if already requested
    if room.rematch_requester_id:
        if room.rematch_requester_id == user.id:
            await query.answer("Вы уже отправили запрос на реванш")
            return
        else:
            # Other player already requested - this means both want rematch!
            # Start new game
            await _start_rematch_game(update, context, room)
            return
    
    # Mark rematch request
    room.rematch_requester_id = user.id
    opponent_id = room.player_b_id if user.id == room.player_a_id else room.player_a_id
    
    # Update requester's message to "waiting"
    try:
        await query.edit_message_caption(
            caption="⏳ *Ожидаем ответ противника...*",
            parse_mode="Markdown",
            reply_markup=rematch_waiting_keyboard(),
        )
    except Exception:
        pass
    
    # Send rematch request to opponent
    if opponent_id:
        try:
            await context.bot.send_message(
                chat_id=opponent_id,
                text=f"🔄 *Противник предлагает реванш!*\n\nХотите сыграть ещё раз?",
                parse_mode="Markdown",
                reply_markup=bind_game_keyboard(rematch_confirm_keyboard(), room),
            )
        except Exception as e:
            logger.error(f"Failed to send rematch request to {opponent_id}: {e}")
    
    await query.answer("Запрос на реванш отправлен")


async def handle_rematch_response(update: Update, context: ContextTypes.DEFAULT_TYPE, response: str) -> None:
    """Handle rematch accept/decline response."""
    query = update.callback_query
    user = update.effective_user
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
    player = get_player(user.id)
    if not player or not player.current_room_id:
        await query.answer("Игра не найдена")
        return
    
    room = get_room(player.current_room_id)
    if not room or room.state != RoomState.COMPLETED or not room.rematch_requester_id or room.rematch_requester_id == user.id:
        await query.answer("Запрос на реванш истёк")
        return
    
    requester_id = room.rematch_requester_id
    
    if response == "yes":
        # Commit successor before the first I/O in _start_rematch_game.
        await _start_rematch_game(update, context, room)
        await query.answer("Начинаем реванш!")
    else:
        # Decline
        room.rematch_requester_id = None
        
        # Update decliner's message
        try:
            await query.edit_message_text(
                MAIN_MENU_TITLE,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            pass
        
        # Notify requester
        if requester_id:
            try:
                await context.bot.send_message(
                    chat_id=requester_id,
                    text="❌ *Противник отказался от реванша*",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(),
                )
            except Exception as e:
                logger.error(f"Failed to notify requester {requester_id}: {e}")
        
        # Clear room association
        delete_room(room.id)
        
        await query.answer("Вы отказались от реванша")


async def _start_rematch_game(update: Update, context: ContextTypes.DEFAULT_TYPE, old_room: Room) -> None:
    """Start a new game as rematch."""
    from state.rooms import create_room
    
    # A player may have started another game while the offer was displayed.
    for uid in (old_room.player_a_id, old_room.player_b_id):
        player = get_player(uid)
        if not player or player.current_room_id != old_room.id:
            await update.callback_query.answer("Реванш уже недоступен")
            return
    # Create new room with same settings
    new_room = create_room(
        mode=old_room.mode,
        board_size=old_room.board_size,
        player_a_id=old_room.player_a_id,
        player_b_id=old_room.player_b_id,
        player_a_emoji=old_room.player_a_emoji,
        player_b_emoji=old_room.player_b_emoji,
        theme=old_room.theme,
    )
    new_room.start_game()
    
    # Update player room associations
    set_player_room(old_room.player_a_id, new_room.id)
    if old_room.player_b_id:
        set_player_room(old_room.player_b_id, new_room.id)
    
    delete_room(old_room.id)

    # Send game state to both players
    recipients = [old_room.player_a_id]
    if old_room.player_b_id:
        recipients.append(old_room.player_b_id)
    await send_game_states(update, context, new_room, recipients)


async def handle_afk_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    choice: str,
) -> None:
    """Handle AFK choice selection."""
    query = update.callback_query
    user = update.effective_user
    
    await query.answer("AFK пока недоступен. Можно продолжить игру или выйти.")


async def handle_leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle player leaving the game."""
    query = update.callback_query
    user = update.effective_user
    
    # Get player's current room
    player = get_player(user.id)
    if player and player.current_room_id:
        room = get_room(player.current_room_id)
        if room:
            delete_room(room.id)
            logger.info(f"Player {user.id} left game {room.id}")
            
            # Notify opponent if PvP
            if not room.is_pve():
                opponent_id = room.player_b_id if user.id == room.player_a_id else room.player_a_id
                if opponent_id:
                    try:
                        # Clear opponent's room state
                        # delete_room already released this room's players.
                        # Notify opponent
                        await context.bot.send_message(
                            chat_id=opponent_id,
                            text="🚫 Соперник покинул игру. Игра завершена.",
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify opponent {opponent_id}: {e}")
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
    # Try to delete the game message
    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"Could not delete game message: {e}")
    
    # Always send menu
    await context.bot.send_message(
        chat_id=user.id,
        text="👋 Вы покинули игру.\n\n" + MAIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
