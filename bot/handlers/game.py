"""
Game handler for in-game interactions.

Handles edge placement, turn management, and game state updates.
All invalid taps receive toast feedback (no silent failures).
"""

import logging
import io
from telegram import Update, InputFile
from telegram.ext import ContextTypes

from telegram_pkg.callback_parser import parse_callback, CallbackAction, matrix_to_edge_id
from telegram_pkg.keyboards import (
    game_board_keyboard, numbered_edge_keyboard, lines_keyboard,
    post_game_keyboard, afk_choice_keyboard
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
from state.rooms import Room, get_room, RoomState
from state.players import get_player, set_player_room
from game.turn import apply_turn, TurnError
from game.scoring import calculate_result
from render.board_renderer import render_board
from ai.easy import EasyBot
from ai.medium import MediumBot
from ai.hard import HardBot
from timers.turn_timer import reset_timeout_counter


logger = logging.getLogger(__name__)


# Bot instances
BOTS = {
    "easy": EasyBot(),
    "medium": MediumBot(),
    "hard": HardBot(),
}


async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle in-game callbacks (edges, noop, rematch, afk)."""
    query = update.callback_query
    user = update.effective_user
    callback = parse_callback(query.data)
    
    logger.info(f"User {user.id} game callback: {query.data}")
    
    # Handle NOOP first (dots, squares, occupied edges)
    if callback.is_noop:
        await handle_noop(update, context, callback.noop_reason)
        return
    
    if callback.action == CallbackAction.EDGE:
        await handle_edge_placement(update, context, callback)
        return
    
    elif callback.is_num:
        # Get player's current room
        player = get_player(user.id)
        if not player or not player.current_room_id:
            await query.answer(toast_game_finished(), show_alert=False)
            return
        room = get_room(player.current_room_id)
        if not room:
            await query.answer(toast_game_finished(), show_alert=False)
            return
        await handle_numbered_edge_placement(update, context, room, callback)
        return
        
    elif callback.action == CallbackAction.PAGE:
        # Update page and refresh
        try:
            page = int(callback.param1)
            room = get_room(get_player(user.id).current_room_id) # Need to get room here
            if room:
                room.current_page = page
                # We must answer callback to stop loading animation
                await query.answer()
                # Resend state (or edit markup if possible, but send_game_state handles full refresh)
                await send_game_state(update, context, room)
            else:
                await query.answer(toast_game_finished(), show_alert=False)
        except Exception as e:
            logger.error(f"Error handling page callback: {e}")
            await query.answer("Ошибка!", show_alert=True)
        return
    
    if callback.action == CallbackAction.REMATCH:
        await query.answer()
        # Check if this is a rematch response (yes/no)
        if callback.param1 in ["yes", "no"]:
            await handle_rematch_response(update, context, callback.param1)
        else:
            await handle_rematch(update, context)
        return
    
    if callback.action == CallbackAction.AFK:
        await query.answer()
        await handle_afk_choice(update, context, callback.param1)
        return
    
    # Handle leave game
    if query.data == "leave":
        await query.answer()
        await handle_leave_game(update, context)
        return
    
    # Unknown callback
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


async def handle_edge_placement(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback,
) -> None:
    """Handle player placing an edge."""
    query = update.callback_query
    user = update.effective_user
    
    # Get player's current room
    player = get_player(user.id)
    if not player or not player.current_room_id:
        await query.answer(toast_game_finished(), show_alert=False)
        return
    
    room = get_room(player.current_room_id)
    if not room:
        await query.answer(toast_game_finished(), show_alert=False)
        return
    
    # Check game state
    if room.state == RoomState.COMPLETED:
        await query.answer(toast_game_finished(), show_alert=False)
        return
    
    if room.state != RoomState.ACTIVE:
        await query.answer(toast_transition_state(), show_alert=False)
        return
    
    # Check if it's player's turn
    if not room.is_player_turn(user.id):
        await query.answer(toast_not_your_turn(), show_alert=False)
        return
    
    # Convert matrix coords to edge_id
    edge_id = matrix_to_edge_id(
        callback.edge_type,
        callback.edge_matrix_row,
        callback.edge_matrix_col,
    )
    
    # Check if edge is already occupied (server-side validation)
    edge = room.board.get_edge(edge_id)
    if edge and edge.is_occupied:
        await query.answer(toast_occupied_edge(), show_alert=False)
        return
    
    # Apply the move
    player_id_str = str(user.id)
    other_player_str = str(room.other_player_id) if room.other_player_id else "bot"
    
    result = apply_turn(
        board=room.board,
        player_id=player_id_str,
        edge_id=edge_id,
        current_player=str(room.current_player_id),
        other_player=other_player_str,
    )
    
    if not result.success:
        if result.error == TurnError.EDGE_OCCUPIED:
            await query.answer(toast_occupied_edge(), show_alert=False)
        else:
            await query.answer("Что-то пошло не так 🤔", show_alert=False)
        return
    
    # Move successful - acknowledge
    await query.answer()
    
    # Reset timeout counter (player made a move)
    reset_timeout_counter(room)
    
    # Check if game is over
    if result.game_over:
        room.complete_game()
        await send_game_over(update, context, room)
        return
    
    # Handle turn transition
    if result.extra_turn:
        room.keep_current_player()
    else:
        room.switch_player()
    
    # If PvE and bot's turn, make bot move
    if room.is_pve() and not room.is_player_turn(user.id):
        await make_bot_move(update, context, room)
    else:
        # Send updated state to current player
        await send_game_state(update, context, room)
        
        # In PvP, also send to the OTHER player
        if not room.is_pve() and room.player_b_id:
            other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
            await send_game_state_new_message(update, context, room, other_player_id)


async def handle_numbered_edge_placement(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback,
) -> None:
    """Handle player placing an edge via numeric input."""
    query = update.callback_query
    user = update.effective_user
    
    # Get player's current room
    player = get_player(user.id)
    if not player or not player.current_room_id:
        await query.answer(toast_game_finished(), show_alert=False)
        return
    
    room = get_room(player.current_room_id)
    if not room:
        await query.answer(toast_game_finished(), show_alert=False)
        return
    
    # Check game state
    if room.state != RoomState.ACTIVE:
        await query.answer(toast_transition_state(), show_alert=False)
        return
    
    # Check if it's player's turn
    if not room.is_player_turn(user.id):
        await query.answer(toast_not_your_turn(), show_alert=False)
        return
        
    # Get edge ID from number
    from game.edge_numbering import get_edge_by_number
    edge_number = callback.edge_number
    
    if not edge_number:
        await query.answer("Неверный номер грани ❌", show_alert=False)
        return
        
    edge_id = get_edge_by_number(room.board, edge_number)
    
    if not edge_id:
        await query.answer("Грань не найдена ❌", show_alert=False)
        return
    
    # Check if edge is already occupied
    edge = room.board.get_edge(edge_id)
    if edge and edge.is_occupied:
        await query.answer(toast_occupied_edge(), show_alert=False)
        return
    
    # Apply the move (reuse logic implicitly by creating result manually or calling apply_turn)
    # Apply the move
    player_id_str = str(user.id)
    other_player_str = str(room.other_player_id) if room.other_player_id else "bot"
    
    result = apply_turn(
        board=room.board,
        player_id=player_id_str,
        edge_id=edge_id,
        current_player=str(room.current_player_id),
        other_player=other_player_str,
    )
    
    if not result.success:
        if result.error == TurnError.EDGE_OCCUPIED:
            await query.answer(toast_occupied_edge(), show_alert=False)
        else:
            await query.answer("Что-то пошло не так 🤔", show_alert=False)
        return
    
    # Move successful - acknowledge
    await query.answer()
    
    # Reset timeout counter
    reset_timeout_counter(room)
    
    # Check if game is over
    if result.game_over:
        room.complete_game()
        await send_game_over(update, context, room)
        return
    
    # Handle turn transition
    if result.extra_turn:
        room.keep_current_player()
    else:
        room.switch_player()
    
    # If PvE and bot's turn, make bot move
    if room.is_pve() and not room.is_player_turn(user.id):
        await make_bot_move(update, context, room)
    else:
        # Send updated state to current player
        await send_game_state(update, context, room)
        
        # In PvP, also send to the OTHER player
        if not room.is_pve() and room.player_b_id:
            other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
            await send_game_state_new_message(update, context, room, other_player_id)


async def handle_numbered_edge_placement(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
    callback,
) -> None:
    """Handle player placing an edge via numeric input."""
    query = update.callback_query
    user = update.effective_user
    
    # Check game state
    if room.state != RoomState.ACTIVE:
        await query.answer(toast_transition_state(), show_alert=False)
        return
    
    # Check if it's player's turn
    if not room.is_player_turn(user.id):
        await query.answer(toast_not_your_turn(), show_alert=False)
        return
        
    # Get edge ID from number
    from game.edge_numbering import get_edge_by_number
    edge_number = callback.edge_number
    
    if not edge_number:
        await query.answer("Неверный номер грани ❌", show_alert=False)
        return
        
    edge_id = get_edge_by_number(room.board, edge_number)
    
    if not edge_id:
        await query.answer("Грань не найдена ❌", show_alert=False)
        return
    
    # Check if edge is already occupied
    edge = room.board.get_edge(edge_id)
    if edge and edge.is_occupied:
        await query.answer(toast_occupied_edge(), show_alert=False)
        return
    
    # Apply the move
    player_id_str = str(user.id)
    other_player_str = str(room.other_player_id) if room.other_player_id else "bot"
    
    result = apply_turn(
        board=room.board,
        player_id=player_id_str,
        edge_id=edge_id,
        current_player=str(room.current_player_id),
        other_player=other_player_str,
    )
    
    if not result.success:
        if result.error == TurnError.EDGE_OCCUPIED:
            await query.answer(toast_occupied_edge(), show_alert=False)
        else:
            await query.answer("Что-то пошло не так 🤔", show_alert=False)
        return
    
    # Move successful - acknowledge
    await query.answer()
    
    # Reset timeout counter
    reset_timeout_counter(room)
    
    # Check if game is over
    if result.game_over:
        room.complete_game()
        await send_game_over(update, context, room)
        return
    
    # Handle turn transition
    if result.extra_turn:
        room.keep_current_player()
    else:
        room.switch_player()
    
    # If PvE and bot's turn, make bot move
    if room.is_pve() and not room.is_player_turn(user.id):
        await make_bot_move(update, context, room)
    else:
        # Send updated state to current player
        await send_game_state(update, context, room)
        
        # In PvP, also send to the OTHER player
        if not room.is_pve() and room.player_b_id:
            other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
            await send_game_state_new_message(update, context, room, other_player_id)


async def make_bot_move(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
) -> None:
    """Execute bot's turn."""
    bot = BOTS.get(room.bot_difficulty, BOTS["medium"])
    
    logger.info(f"Bot turn started. Available edges: {len(room.board.get_available_edges())}")
    
    # Bot may get multiple turns (chains)
    moves_made = 0
    while True:
        available = room.board.get_available_edges()
        logger.info(f"Bot choosing from {len(available)} edges")
        
        edge_id = bot.choose_edge(room.board)
        if not edge_id:
            logger.info(f"Bot returned None, no more moves")
            break
        
        logger.info(f"Bot chose edge: {edge_id}")
        
        result = apply_turn(
            board=room.board,
            player_id="bot",
            edge_id=edge_id,
            current_player="bot",
            other_player=str(room.player_a_id),
        )
        
        if not result.success:
            logger.warning(f"Bot move failed: {result.error}")
            break
        
        moves_made += 1
        logger.info(f"Bot move #{moves_made} success. Captures: {len(result.captures)}, Extra turn: {result.extra_turn}")
        
        if result.game_over:
            room.complete_game()
            await send_game_over(update, context, room)
            return
        
        if not result.extra_turn:
            room.switch_player()
            break
    
    logger.info(f"Bot finished. Made {moves_made} moves. Now player's turn.")
    # Send updated game state
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
        opponent_player = get_player(room.other_player_id)
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
        reply_markup=keyboard,
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
                reply_markup=keyboard,
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
        reply_markup=keyboard,
    )
    room.set_message_id(user_id, sent_message.message_id)


async def send_game_over(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
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
    if not room.is_pve() and room.player_b_id:
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
    
    # Clear player's room
    set_player_room(user_id, None)
    
    await context.bot.send_photo(
        chat_id=user_id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="HTML",
        reply_markup=post_game_keyboard(can_rematch=True),
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
        )
        new_room.start_game()
        set_player_room(user.id, new_room.id)
        
        await query.answer("Начинаем новую игру!")
        await send_game_state_new_message(update, context, new_room, user.id)
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
                reply_markup=rematch_confirm_keyboard(),
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
    if not room or not room.rematch_requester_id:
        await query.answer("Запрос на реванш истёк")
        return
    
    requester_id = room.rematch_requester_id
    
    if response == "yes":
        # Accept - start new game
        await query.answer("Начинаем реванш!")
        await _start_rematch_game(update, context, room)
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
        clear_player_room(user.id)
        if requester_id:
            clear_player_room(requester_id)
        
        await query.answer("Вы отказались от реванша")


async def _start_rematch_game(update: Update, context: ContextTypes.DEFAULT_TYPE, old_room: Room) -> None:
    """Start a new game as rematch."""
    from state.rooms import create_room
    
    # Create new room with same settings
    new_room = create_room(
        mode=old_room.mode,
        board_size=old_room.board_size,
        player_a_id=old_room.player_a_id,
        player_b_id=old_room.player_b_id,
        player_a_emoji=old_room.player_a_emoji,
        player_b_emoji=old_room.player_b_emoji,
    )
    new_room.start_game()
    
    # Update player room associations
    set_player_room(old_room.player_a_id, new_room.id)
    if old_room.player_b_id:
        set_player_room(old_room.player_b_id, new_room.id)
    
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
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
    if choice == "bot":
        # Continue with bot taking over opponent
        # TODO: Implement bot takeover
        pass
    elif choice == "surrender":
        # TODO: Implement surrender
        pass
    
    await query.edit_message_text(
        MAIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def handle_leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle player leaving the game."""
    query = update.callback_query
    user = update.effective_user
    
    # Get player's current room
    player = get_player(user.id)
    if player and player.current_room_id:
        room = get_room(player.current_room_id)
        if room:
            room.state = RoomState.ABANDONED
            logger.info(f"Player {user.id} left game {room.id}")
            
            # Notify opponent if PvP
            if not room.is_pve():
                opponent_id = room.player_b_id if user.id == room.player_a_id else room.player_a_id
                if opponent_id:
                    try:
                        # Clear opponent's room state
                        set_player_room(opponent_id, None)
                        # Notify opponent
                        await context.bot.send_message(
                            chat_id=opponent_id,
                            text="🚫 Соперник покинул игру. Игра завершена.",
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify opponent {opponent_id}: {e}")
    
    # Clear player's room
    set_player_room(user.id, None)
    
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
