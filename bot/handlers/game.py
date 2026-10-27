"""
Game handler for in-game interactions.

Handles edge placement, turn management, and game state updates.
All invalid taps receive toast feedback (no silent failures).
"""

import logging
import io
from telegram import Update, InputFile
from telegram.error import TelegramError
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
                or user.id not in (room.player_a_id, room.player_b_id)
                or callback.version != room.state_version):
            await query.answer("Кнопка устарела. Используйте текущее поле.")
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
            if room.input_mode != "lines" or not 0 <= page < lines_page_count(room.board):
                await query.answer("Неверная страница")
                return
            room.current_page = page
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
        await send_game_state(update, context, room)
        if not room.is_pve() and room.player_b_id:
            other = room.player_b_id if user.id == room.player_a_id else room.player_a_id
            await send_game_state_new_message(update, context, room, other)


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


async def send_game_state(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
) -> None:
    """Send current game state to player."""
    query = update.callback_query
    user = update.effective_user
    
    is_your_turn = room.is_player_turn(user.id)
    
    # Determine opponent name
    if room.is_pve():
        difficulty_names = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
        opponent = f"🤖 Бот ({difficulty_names.get(room.bot_difficulty, 'Средний')})"
    else:
        opponent_id = room.player_b_id if user.id == room.player_a_id else room.player_a_id
        opponent_player = get_player(opponent_id)
        opponent = opponent_player.display_name if opponent_player else "Соперник"
    
    # Generate turn message
    if is_your_turn:
        turn_msg = YOUR_TURN
    elif room.is_pve():
        turn_msg = BOT_TURN
    else:
        turn_msg = OPPONENT_TURN
    
    # Calculate current scores
    from game.capture import count_player_squares
    
    player_a_str = str(room.player_a_id)
    player_b_str = str(room.player_b_id) if room.player_b_id else "bot"
    
    score_a = count_player_squares(room.board, player_a_str)
    score_b = count_player_squares(room.board, player_b_str)
    
    # Determine which score is "yours" vs "opponent"
    user_is_player_a = user.id == room.player_a_id
    if user_is_player_a:
        your_score = score_a
        opponent_score = score_b
        your_emoji = room.player_a_emoji
        opponent_emoji = room.player_b_emoji
    else:
        your_score = score_b
        opponent_score = score_a
        your_emoji = room.player_b_emoji
        opponent_emoji = room.player_a_emoji
    
    message = GAME_STATUS.format(
        your_emoji=your_emoji,
        your_score=your_score,
        opponent_score=opponent_score,
        opponent_emoji=opponent_emoji,
        opponent=opponent,
        turn_message=turn_msg,
    )
    
    if room.input_mode == "numbered":
        message += "\n" + NUMBERED_MODE_HELP
    
    # Render board image
    player_emojis = {
        player_a_str: room.player_a_emoji,
        player_b_str: room.player_b_emoji,
    }
    
    image_bytes = render_board(
        board=room.board,
        theme_name=room.theme,
        player_a_id=player_a_str,
        player_b_id=player_b_str,
        player_emojis=player_emojis,
        show_numbers=(room.input_mode in ["numbered", "lines"]),
    )
    
    # Generate keyboard
    if room.input_mode == "numbered":
        keyboard = numbered_edge_keyboard(room.board)
    elif room.input_mode == "lines":
        keyboard = lines_keyboard(
            room.board, 
            player_a_id=player_a_str,
            player_b_id=player_b_str, 
            page=room.current_page
        )
    else:
        keyboard = game_board_keyboard(
            room.board,
            player_a_id=player_a_str,
            player_b_id=player_b_str,
            player_emojis=player_emojis,
        )
    
    # Delete old message and send new one with image and keyboard
    try:
        await query.message.delete()
    except Exception:
        pass
    
    sent_message = await context.bot.send_photo(
        chat_id=user.id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="HTML",
        reply_markup=bind_game_keyboard(keyboard, room),
    )
    
    # Store message_id for future edits
    room.set_message_id(user.id, sent_message.message_id)


async def send_game_state_new_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room,
    user_id: int,
) -> None:
    """Send or edit game state message for a player."""
    from game.capture import count_player_squares
    from telegram import InputMediaPhoto
    
    is_your_turn = room.is_player_turn(user_id)
    user_is_player_a = user_id == room.player_a_id
    
    # Determine opponent name
    if room.is_pve():
        difficulty_names = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
        opponent = f"🤖 Бот ({difficulty_names.get(room.bot_difficulty, 'Средний')})"
    else:
        # Get the OTHER player's info
        if user_is_player_a:
            opponent_id = room.player_b_id
        else:
            opponent_id = room.player_a_id
        opponent_player = get_player(opponent_id) if opponent_id else None
        opponent = opponent_player.display_name if opponent_player else "Соперник"
    
    # Generate turn message
    if is_your_turn:
        turn_msg = YOUR_TURN
    else:
        turn_msg = OPPONENT_TURN
    
    # Calculate current scores
    player_a_str = str(room.player_a_id)
    player_b_str = str(room.player_b_id) if room.player_b_id else "bot"
    
    score_a = count_player_squares(room.board, player_a_str)
    score_b = count_player_squares(room.board, player_b_str)
    
    if user_is_player_a:
        your_score = score_a
        opponent_score = score_b
        your_emoji = room.player_a_emoji
        opponent_emoji = room.player_b_emoji
    else:
        your_score = score_b
        opponent_score = score_a
        your_emoji = room.player_b_emoji
        opponent_emoji = room.player_a_emoji
    
    message = GAME_STATUS.format(
        your_emoji=your_emoji,
        your_score=your_score,
        opponent_score=opponent_score,
        opponent_emoji=opponent_emoji,
        opponent=opponent,
        turn_message=turn_msg,
    )
    
    if room.input_mode == "numbered":
        message += "\n" + NUMBERED_MODE_HELP
    
    # Render board image
    player_emojis = {
        player_a_str: room.player_a_emoji,
        player_b_str: room.player_b_emoji,
    }
    
    image_bytes = render_board(
        board=room.board,
        theme_name=room.theme,
        player_a_id=player_a_str,
        player_b_id=player_b_str,
        player_emojis=player_emojis,
        show_numbers=(room.input_mode in ["numbered", "lines"]),
    )
    
    # Generate keyboard
    if room.input_mode == "numbered":
        keyboard = numbered_edge_keyboard(room.board)
    elif room.input_mode == "lines":
        keyboard = lines_keyboard(
            room.board, 
            player_a_id=player_a_str,
            player_b_id=player_b_str, 
            page=room.current_page
        )
    else:
        keyboard = game_board_keyboard(
            room.board,
            player_a_id=player_a_str,
            player_b_id=player_b_str,
            player_emojis=player_emojis,
        )
    
    # Try to edit existing message, or send new one
    existing_msg_id = room.get_message_id(user_id)
    
    if existing_msg_id:
        try:
            # Edit existing message with new photo and caption
            await context.bot.edit_message_media(
                chat_id=user_id,
                message_id=existing_msg_id,
                media=InputMediaPhoto(
                    media=io.BytesIO(image_bytes),
                    caption=message,
                    parse_mode="HTML",
                ),
                reply_markup=bind_game_keyboard(keyboard, room),
            )
            return  # Success, no need to send new
        except Exception as e:
            logger.debug(f"Failed to edit message {existing_msg_id}: {e}")
            # Fall through to send new message
    
    # Send new message and store its ID
    sent_message = await context.bot.send_photo(
        chat_id=user_id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="HTML",
        reply_markup=bind_game_keyboard(keyboard, room),
    )
    room.set_message_id(user_id, sent_message.message_id)


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
    
    # Render final board once
    player_emojis = {
        player_a_str: room.player_a_emoji,
        player_b_str: room.player_b_emoji,
    }
    
    image_bytes = render_board(
        board=room.board,
        theme_name=room.theme,
        player_a_id=player_a_str,
        player_b_id=player_b_str,
        player_emojis=player_emojis,
    )
    
    # Delete the initiator's old message
    try:
        await query.message.delete()
    except Exception:
        pass
    
    # Send to current user (who made the last move)
    await _send_game_over_to_player(context, room, result, user.id, image_bytes)
    
    # In PvP, also send to the OTHER player
    if not only_current_user and not room.is_pve() and room.player_b_id:
        other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
        await _send_game_over_to_player(context, room, result, other_player_id, image_bytes)


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
    
    # Keep completed match association until rematch, replacement or TTL cleanup.
    
    await context.bot.send_photo(
        chat_id=user_id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="HTML",
        reply_markup=bind_game_keyboard(post_game_keyboard(can_rematch=True), room),
    )


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
    await send_game_state_new_message(update, context, new_room, old_room.player_a_id)
    if old_room.player_b_id:
        await send_game_state_new_message(update, context, new_room, old_room.player_b_id)


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
