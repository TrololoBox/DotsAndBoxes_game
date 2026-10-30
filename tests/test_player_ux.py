from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image
from telegram.error import BadRequest, NetworkError

from bot.handlers import game, play, start
from game.board import Board
from game.edge_numbering import get_edge_numbers, get_number_for_edge
from render.board_renderer import render_board
from state.players import get_or_create_player, get_player, set_player_room
from state.queues import is_in_queue, join_queue
from state.rooms import GameMode, RoomState, create_room, get_room
from telegram_pkg.keyboards import bind_game_keyboard, lines_page_count, numbered_edge_keyboard
from telegram_pkg.callback_parser import parse_callback


def active_room(size=3, mode=GameMode.PVE):
    for uid in (1, 2):
        get_or_create_player(uid, f"u{uid}", f"Player {uid}")
    r = create_room(mode, size, 1, 2 if mode != GameMode.PVE else None, bot_difficulty="easy")
    r.start_game()
    set_player_room(1, r.id)
    if r.player_b_id:
        set_player_room(2, r.id)
    return r


def wire(r, raw):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return bind_game_keyboard(InlineKeyboardMarkup([[InlineKeyboardButton("x", callback_data=raw)]]), r).inline_keyboard[0][0].callback_data


@pytest.mark.parametrize("size", [3, 10304, 10305, 10404, 10505, 10606])
def test_number_on_button_selects_same_edge_for_every_size(size):
    r = active_room(size)
    assert r.input_mode == "numbered"
    mapping = get_edge_numbers(r.board)
    def displayed():
        result = {}
        for page in range(lines_page_count(r.board)):
            kb = numbered_edge_keyboard(r.board, page)
            assert all(len(row) <= 6 for row in kb.inline_keyboard)
            for row in kb.inline_keyboard:
                for button in row:
                    cb = parse_callback(button.callback_data)
                    if cb.is_num:
                        assert button.text == str(cb.edge_number)
                        result[cb.edge_number] = button.text
        return result
    before = displayed()
    assert set(before) == set(mapping.values())
    eight = next(edge for edge, number in mapping.items() if number == 8)
    r.apply_move("1", eight)
    after = displayed()
    assert after == {n: label for n, label in before.items() if n != 8}
    assert get_edge_numbers(r.board) == mapping


@pytest.mark.parametrize("theme", ["classic", "forest", "night"])
@pytest.mark.parametrize("edge,halo_pixel,owner_pixel", [
    # Sample the visible line, away from the wider numbered star badge.
    ("h_0_0", (108, 32), (108, 40)),
    ("v_0_0", (32, 52), (40, 52)),
])
def test_last_move_visibly_highlighted_without_losing_ownership(theme, edge, halo_pixel, owner_pixel):
    board = Board(3, 3)
    board.place_edge(edge, "1")
    ordinary = Image.open(BytesIO(render_board(board, theme, "1", "2", show_numbers=True))).convert("RGB")
    last = Image.open(BytesIO(render_board(board, theme, "1", "2", show_numbers=True,
                                         last_edge_id=edge, recent_edge_ids=[edge]))).convert("RGB")
    assert ordinary.getpixel(halo_pixel) != last.getpixel(halo_pixel)
    assert last.getpixel(halo_pixel) == (255, 213, 79)
    assert last.getpixel(owner_pixel) == ordinary.getpixel(owner_pixel)


@pytest.mark.asyncio
async def test_quick_start_is_one_tap_to_real_small_game(transport):
    ctx, update = transport
    await start.main_menu_callback(update(1, "menu:quick"), ctx)
    r = get_room(get_player(1).current_room_id)
    assert r.mode == GameMode.PVE and r.bot_difficulty == "easy"
    assert (r.board_width, r.board_height) == (3, 3)
    assert r.state == RoomState.ACTIVE
    assert ctx.bot.send_photo.await_count == 1
    assert "номер" in ctx.bot.send_photo.call_args.kwargs["caption"]


@pytest.mark.asyncio
async def test_quick_start_keeps_existing_match_and_offers_resume(transport):
    ctx, update = transport
    r = active_room()
    r.apply_move("1", "h_0_0")
    u = update(1, "menu:quick")
    await start.main_menu_callback(u, ctx)
    assert get_player(1).current_room_id == r.id
    assert r.board.get_edge("h_0_0").owner == "1"
    kb = u.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    assert any(b.callback_data == "menu:resume" for row in kb.inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_menu_from_finished_photo_uses_caption_not_text(transport):
    ctx, update = transport
    r = active_room()
    r.complete_game()
    u = update(1, "menu:main")
    u.callback_query.message.photo = [object()]
    u.callback_query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")
    await start.main_menu_callback(u, ctx)
    u.callback_query.edit_message_caption.assert_awaited_once()
    u.callback_query.edit_message_text.assert_not_awaited()
    await start.main_menu_callback(update(1, "menu:quick"), ctx)
    assert get_player(1).current_room_id != r.id


@pytest.mark.asyncio
async def test_game_message_is_edited_for_move_and_result(transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    u = update(1)
    await game.send_game_state(u, ctx, r)
    first = r.message_a_id
    r.apply_move("1", "h_0_0")
    await game.send_game_state(u, ctx, r)
    assert r.message_a_id == first
    assert ctx.bot.send_photo.await_count == 1
    assert ctx.bot.edit_message_media.await_count == 1
    r.complete_game()
    await game.send_game_over(u, ctx, r, only_current_user=True)
    assert r.message_a_id == first and ctx.bot.send_photo.await_count == 1
    assert ctx.bot.edit_message_media.await_count == 2
    u.callback_query.message.delete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error,replaced", [
    (BadRequest("Message is not modified"), False),
    (BadRequest("Message to edit not found"), True),
])
async def test_photo_edit_errors_do_not_duplicate_a_live_message(error, replaced, transport):
    ctx, update = transport
    r = active_room()
    r.message_a_id = 55
    ctx.bot.edit_message_media.side_effect = error
    await game.send_game_state(update(1), ctx, r)
    assert ctx.bot.send_photo.await_count == int(replaced)


@pytest.mark.asyncio
async def test_network_failure_does_not_spawn_a_second_game_message(transport):
    ctx, update = transport
    r = active_room()
    r.message_a_id = 55
    ctx.bot.edit_message_media.side_effect = NetworkError("delivery offline")
    with pytest.raises(NetworkError):
        await game.send_game_state(update(1), ctx, r)
    ctx.bot.send_photo.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_chain_has_exact_last_edge_and_human_move_summary(transport, monkeypatch):
    ctx, update = transport
    r = active_room()
    for edge in ("h_0_0", "h_1_0", "v_0_0", "h_0_2", "h_1_2", "v_0_2"):
        r.board.place_edge(edge, "1")
    r.apply_move("1", "h_2_1")
    chain = ["v_0_1", "v_0_3", "h_2_0"]
    moves = iter(chain)
    monkeypatch.setitem(game.BOTS, "easy", SimpleNamespace(choose_edge=lambda board: next(moves)))
    await game.make_bot_move(update(1), ctx, r)
    assert r.recent_edge_ids == chain and r.last_move_edge_id == chain[-1]
    assert r.recent_captures == 2 and r.current_player_id == 1
    caption = ctx.bot.send_photo.call_args.kwargs["caption"]
    assert f"Бот — №{get_number_for_edge(r.board, chain[-1])}" in caption
    assert "Твоя последняя линия" in caption and "Серия ходов" in caption
    assert "+2 очк." in caption


@pytest.mark.asyncio
async def test_exit_asks_first_and_cancel_keeps_board(transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    r.apply_move("1", "h_0_0")
    await game.game_callback(update(1, wire(r, "leave:ask")), ctx)
    assert get_room(r.id) is r
    await game.game_callback(update(1, wire(r, "leave:no")), ctx)
    assert get_room(r.id) is r and r.board.get_edge("h_0_0").owner == "1"
    await game.game_callback(update(1, wire(r, "leave:yes")), ctx)
    assert get_room(r.id) is None and get_player(2).current_room_id is None


@pytest.mark.asyncio
async def test_old_exit_confirmation_cannot_end_a_new_turn(transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    old = wire(r, "leave:yes")
    r.apply_move("1", "h_0_0")
    await game.game_callback(update(1, old), ctx)
    assert get_room(r.id) is r


@pytest.mark.asyncio
async def test_pvp_number_pages_are_independent(transport):
    ctx, update = transport
    r = active_room(10606, GameMode.PVP_FRIEND)
    await game.game_callback(update(1, wire(r, "pg:1")), ctx)
    await game.game_callback(update(2, wire(r, "pg:0")), ctx)
    assert r.pages_by_player == {1: 1, 2: 0}
    assert r.state_version == 1


@pytest.mark.asyncio
async def test_friend_share_contains_joinable_link_without_inline_mode(transport):
    ctx, update = transport
    get_or_create_player(1, "", "Player")
    u = update(1)
    await play.create_friend_invite(u, ctx, 3)
    r = get_room(get_player(1).current_room_id)
    kb = u.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    share = kb.inline_keyboard[0][0]
    assert share.switch_inline_query is None
    params = parse_qs(urlparse(share.url).query)
    assert params["url"] == [f"https://t.me/offline_test_bot?start=invite_{r.invite_code}"]
    await start.handle_invite_join(update(2), ctx, r.invite_code)
    assert r.state == RoomState.ACTIVE and r.player_b_id == 2


@pytest.mark.asyncio
async def test_rectangle_queue_uses_human_dimensions_and_quick_start_cancels_search(transport):
    ctx, update = transport
    ctx.user_data[play.PENDING_MODE_KEY] = "pvp_world"
    u = update(1)
    await play.handle_size_selection(u, ctx, 10304)
    text = u.callback_query.edit_message_text.call_args.args[0]
    assert "3×4" in text and "10304" not in text
    assert is_in_queue(1)
    await play.start_quick_game(update(1), ctx)
    assert not is_in_queue(1)
    assert get_room(get_player(1).current_room_id).mode == GameMode.PVE


@pytest.mark.asyncio
async def test_cancel_search_from_photo_menu(transport):
    ctx, update = transport
    join_queue(1, 3)
    u = update(1, "cq")
    u.callback_query.message.photo = [object()]
    u.callback_query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")
    await play.handle_cancel_queue(u, ctx)
    assert not is_in_queue(1)
    u.callback_query.edit_message_caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_invite_link_survives_menu_and_resume(transport):
    ctx, update = transport
    get_or_create_player(1, "", "Player")
    await play.create_friend_invite(update(1), ctx, 3)
    r = get_room(get_player(1).current_room_id)
    u = update(1, "menu:resume")
    u.callback_query.message.photo = [object()]
    await start.main_menu_callback(u, ctx)
    caption = u.callback_query.edit_message_caption.call_args.kwargs["caption"]
    assert f"?start=invite_{r.invite_code}" in caption
    assert get_room(r.id) is r and r.state == RoomState.PENDING
