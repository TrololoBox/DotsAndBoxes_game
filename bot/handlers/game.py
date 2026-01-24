"""
Game handler for in-game interactions.

Handles edge placement, turn management, and game state updates.
All invalid taps receive toast feedback (no silent failures).
"""

import logging
import io
from telegram import Update
from telegram.ext import ContextTypes

from telegram_pkg.callback_parser import parse_callback, CallbackAction, matrix_to_edge_id
from telegram_pkg.keyboards import (
    game_board_keyboard, numbered_edge_keyboard, lines_keyboard,
    post_game_keyboard
)
from telegram_pkg.messages import (
    GAME_STATUS, YOUR_TURN, OPPONENT_TURN, BOT_TURN,
    GAME_OVER_WIN, GAME_OVER_LOSE, GAME_OVER_DRAW,
    NUMBERED_MODE_HELP,
    LEAVE_GAME_MESSAGE,
    BOT_DIFFICULTY_NAMES,
    BOT_NAME_TEMPLATE,
    OPPONENT_FALLBACK,
    BOT_DIFFICULTY_DEFAULT,
)
from telegram_pkg.toasts import (
    toast_tap_dot,
    toast_tap_square,
    toast_unknown_error,
    toast_ad_placeholder,
)
from telegram_pkg.ux import toast_for_error
from state.rooms import Room, get_room
from state.players import get_player, set_player_room
from game.scoring import calculate_result
from render.board_renderer import render_board
from ai.easy import EasyBot
from ai.medium import MediumBot
from ai.hard import HardBot
from state.engine import (
    apply_edge_move,
    apply_numbered_move,
    apply_bot_edge,
    update_page,
    abandon_room,
)
from game.lines_pagination import get_lines_max_page
from state.logging_utils import log_event


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
    
    if callback.action == CallbackAction.LEAVE:
        await query.answer()
        await handle_leave_game(update, context)
        return

    # Handle NOOP first (dots, squares, occupied edges)
    if callback.is_noop:
        await handle_noop(update, context, callback.noop_reason)
        return
    
    if callback.action == CallbackAction.EDGE:
        await handle_edge_placement(update, context, callback)
        return
    
    elif callback.is_num:
        await handle_numbered_edge_placement(update, context, callback)
        return
        
    elif callback.action == CallbackAction.PAGE:
        await handle_page_change(update, context, callback)
        return
    
    if callback.action == CallbackAction.REMATCH:
        await query.answer()
        await handle_rematch(update, context)
        return
    
    if callback.action == CallbackAction.AFK:
        await query.answer()
        await handle_afk_choice(update, context, callback)
        return
    
    log_event(
        logger,
        logging.WARNING,
        "action_rejected",
        game_id=None,
        room_id=None,
        user_id=user.id,
        reason="unknown_callback",
        data=query.data,
    )
    await query.answer(toast_unknown_error(), show_alert=False)


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
        await query.answer(toast_for_error("edge_occupied"), show_alert=False)
    
    elif reason == "ad":
        await query.answer(toast_ad_placeholder(), show_alert=False)

    elif reason == "page":
        await query.answer(toast_for_error("action_rejected"), show_alert=False)
    
    else:
        await query.answer(toast_unknown_error(), show_alert=False)


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
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=None,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return
    
    room = get_room(player.current_room_id)
    if not room:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=player.current_room_id,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    if callback.version is None:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="stale_callback",
        )
        await query.answer(toast_for_error("stale_callback"), show_alert=False)
        return

    if callback.edge_type is None or callback.edge_matrix_row is None or callback.edge_matrix_col is None:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="invalid_edge",
        )
        await query.answer(toast_for_error("invalid_edge"), show_alert=False)
        return

    # Convert matrix coords to edge_id
    edge_id = matrix_to_edge_id(
        callback.edge_type,
        callback.edge_matrix_row,
        callback.edge_matrix_col,
    )

    result = apply_edge_move(room, user.id, edge_id, callback.version)
    if not result.ok:
        await query.answer(toast_for_error(result.error_code), show_alert=False)
        return
    
    # Move successful - acknowledge
    await query.answer()
    
    # Check if game is over
    if result.game_over:
        await send_game_over(update, context, room)
        return
    
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

    player = get_player(user.id)
    if not player or not player.current_room_id:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=None,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    room = get_room(player.current_room_id)
    if not room:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=player.current_room_id,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    if callback.version is None:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="stale_callback",
        )
        await query.answer(toast_for_error("stale_callback"), show_alert=False)
        return

    result = apply_numbered_move(room, user.id, callback.edge_number, callback.version)
    if not result.ok:
        await query.answer(toast_for_error(result.error_code), show_alert=False)
        return

    await query.answer()

    if result.game_over:
        await send_game_over(update, context, room)
        return

    if room.is_pve() and not room.is_player_turn(user.id):
        await make_bot_move(update, context, room)
    else:
        await send_game_state(update, context, room)

        if not room.is_pve() and room.player_b_id:
            other_player_id = room.player_a_id if user.id == room.player_b_id else room.player_b_id
            await send_game_state_new_message(update, context, room, other_player_id)


async def handle_page_change(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback,
) -> None:
    """Handle pagination callbacks."""
    query = update.callback_query
    user = update.effective_user

    player = get_player(user.id)
    if not player or not player.current_room_id:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=None,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    room = get_room(player.current_room_id)
    if not room:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=player.current_room_id,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    if callback.version is None:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="stale_callback",
        )
        await query.answer(toast_for_error("stale_callback"), show_alert=False)
        return

    if room.input_mode != "lines":
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="action_rejected",
        )
        await query.answer(toast_for_error("action_rejected"), show_alert=False)
        return

    try:
        page = int(callback.param1) if callback.param1 is not None else None
    except ValueError:
        page = None

    max_page = get_lines_max_page(room.board)
    result = update_page(room, user.id, page, callback.version, max_page)
    if not result.ok:
        await query.answer(toast_for_error(result.error_code), show_alert=False)
        return

    await query.answer()
    await send_game_state(update, context, room)


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
        
        result = apply_bot_edge(room, edge_id)
        
        if not result.ok:
            logger.warning(f"Bot move failed: {result.error_code}")
            break
        
        moves_made += 1
        captures = len(result.turn_result.captures) if result.turn_result else 0
        extra_turn = result.turn_result.extra_turn if result.turn_result else False
        logger.info(
            f"Bot move #{moves_made} success. Captures: {captures}, Extra turn: {extra_turn}"
        )
        
        if result.game_over:
            await send_game_over(update, context, room)
            return

        if not result.turn_result or not result.turn_result.extra_turn:
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
        opponent = BOT_NAME_TEMPLATE.format(
            difficulty=BOT_DIFFICULTY_NAMES.get(room.bot_difficulty, BOT_DIFFICULTY_DEFAULT)
        )
    else:
        opponent_player = get_player(room.other_player_id)
        opponent = opponent_player.display_name if opponent_player else OPPONENT_FALLBACK
    
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
        keyboard = numbered_edge_keyboard(room.board, room.state_version)
    elif room.input_mode == "lines":
        keyboard = lines_keyboard(
            room.board,
            player_a_id=player_a_str,
            state_version=room.state_version,
            player_b_id=player_b_str,
            page=room.current_page,
        )
    else:
        keyboard = game_board_keyboard(
            room.board,
            player_a_id=player_a_str,
            player_b_id=player_b_str,
            state_version=room.state_version,
            player_emojis=player_emojis,
        )
    
    # Delete old message and send new one with image and keyboard
    try:
        await query.message.delete()
    except Exception:
        pass
    
    try:
        sent_message = await context.bot.send_photo(
            chat_id=user.id,
            photo=io.BytesIO(image_bytes),
            caption=message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "delivery_failed",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            state_version=room.state_version,
            move_number=room.move_number,
            error=str(exc),
        )
        abandon_room(room, user.id, "delivery_failed")
        return
    
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
        opponent = BOT_NAME_TEMPLATE.format(
            difficulty=BOT_DIFFICULTY_NAMES.get(room.bot_difficulty, BOT_DIFFICULTY_DEFAULT)
        )
    else:
        # Get the OTHER player's info
        if user_is_player_a:
            opponent_id = room.player_b_id
        else:
            opponent_id = room.player_a_id
        opponent_player = get_player(opponent_id) if opponent_id else None
        opponent = opponent_player.display_name if opponent_player else OPPONENT_FALLBACK
    
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
        keyboard = numbered_edge_keyboard(room.board, room.state_version)
    elif room.input_mode == "lines":
        keyboard = lines_keyboard(
            room.board,
            player_a_id=player_a_str,
            state_version=room.state_version,
            player_b_id=player_b_str,
            page=room.current_page,
        )
    else:
        keyboard = game_board_keyboard(
            room.board,
            player_a_id=player_a_str,
            player_b_id=player_b_str,
            state_version=room.state_version,
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
    try:
        sent_message = await context.bot.send_photo(
            chat_id=user_id,
            photo=io.BytesIO(image_bytes),
            caption=message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "delivery_failed",
            game_id=room.id,
            room_id=room.id,
            user_id=user_id,
            state_version=room.state_version,
            move_number=room.move_number,
            error=str(exc),
        )
        abandon_room(room, user_id, "delivery_failed")
        return
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
    
    try:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=io.BytesIO(image_bytes),
            caption=message,
            parse_mode="HTML",
            reply_markup=post_game_keyboard(can_rematch=True),
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "delivery_failed",
            game_id=room.id,
            room_id=room.id,
            user_id=user_id,
            state_version=room.state_version,
            move_number=room.move_number,
            error=str(exc),
        )


async def handle_rematch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rematch request."""
    query = update.callback_query
    user = update.effective_user
    
    # For now, return to menu
    # TODO: Implement full rematch with room recreation
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
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


async def handle_afk_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    callback,
) -> None:
    """Handle AFK choice selection."""
    query = update.callback_query
    user = update.effective_user
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE

    player = get_player(user.id)
    if not player or not player.current_room_id:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=None,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    room = get_room(player.current_room_id)
    if not room:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=player.current_room_id,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return

    if callback.version is None or callback.version != room.state_version:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=room.id,
            room_id=room.id,
            user_id=user.id,
            reason="stale_callback",
            expected_version=callback.version,
            state_version=room.state_version,
        )
        await query.answer(toast_for_error("stale_callback"), show_alert=False)
        return

    if callback.param1 == "surrender":
        abandon_room(room, user.id, "afk_surrender")
    else:
        abandon_room(room, user.id, "afk_continue_unavailable")

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
            abandon_room(room, user.id, "player_left")
        else:
            log_event(
                logger,
                logging.WARNING,
                "action_rejected",
                game_id=None,
                room_id=player.current_room_id,
                user_id=user.id,
                reason="room_not_found",
            )
            await query.answer(toast_for_error("room_not_found"), show_alert=False)
            return
    else:
        log_event(
            logger,
            logging.WARNING,
            "action_rejected",
            game_id=None,
            room_id=None,
            user_id=user.id,
            reason="room_not_found",
        )
        await query.answer(toast_for_error("room_not_found"), show_alert=False)
        return
    
    # Clear player's room
    set_player_room(user.id, None)
    
    from telegram_pkg.keyboards import main_menu_keyboard
    from telegram_pkg.messages import MAIN_MENU_TITLE
    
    try:
        await query.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        chat_id=user.id,
        text=LEAVE_GAME_MESSAGE.format(main_menu=MAIN_MENU_TITLE),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
