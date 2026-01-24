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
from telegram_pkg.keyboards import game_board_keyboard, post_game_keyboard, afk_choice_keyboard
from telegram_pkg.messages import (
    GAME_STATUS, YOUR_TURN, OPPONENT_TURN, BOT_TURN,
    CAPTURE_SINGLE, CAPTURE_DOUBLE, GAME_OVER_WIN, GAME_OVER_LOSE, GAME_OVER_DRAW,
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
    
    if callback.action == CallbackAction.REMATCH:
        await query.answer()
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
    )
    
    # Generate keyboard
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
    
    await context.bot.send_photo(
        chat_id=user.id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def send_game_state_new_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room,
    user_id: int,
) -> None:
    """Send game state as new message (for invite joins, not callback edits)."""
    from game.capture import count_player_squares
    
    is_your_turn = room.is_player_turn(user_id)
    user_is_player_a = user_id == room.player_a_id
    
    # Determine opponent name
    if room.is_pve():
        difficulty_names = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
        opponent = f"🤖 Бот ({difficulty_names.get(room.bot_difficulty, 'Средний')})"
    else:
        opponent_player = get_player(room.other_player_id if user_is_player_a else room.player_a_id)
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
    )
    
    # Generate keyboard
    keyboard = game_board_keyboard(
        room.board,
        player_a_id=player_a_str,
        player_b_id=player_b_str,
        player_emojis=player_emojis,
    )
    
    await context.bot.send_photo(
        chat_id=user_id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def send_game_over(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    room: Room,
) -> None:
    """Send game over message."""
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
    
    # Determine message based on result
    user_is_player_a = user.id == room.player_a_id
    
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
    
    # Render final board
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
    
    # Clear player's room
    set_player_room(user.id, None)
    
    try:
        await query.message.delete()
    except Exception:
        pass
    
    await context.bot.send_photo(
        chat_id=user.id,
        photo=io.BytesIO(image_bytes),
        caption=message,
        parse_mode="Markdown",
        reply_markup=post_game_keyboard(can_rematch=True),
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
        text="👋 Вы покинули игру.\n\n" + MAIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
