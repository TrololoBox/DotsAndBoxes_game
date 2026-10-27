import asyncio
from datetime import datetime, timedelta

import pytest

from bot.handlers import game, play, start
from game.board import Board
from game.capture import count_player_squares
from game.scoring import calculate_result
from game.turn import apply_turn, TurnError
from state.rooms import create_room, get_room, get_room_by_invite, get_all_rooms, GameMode, RoomState
from state.players import get_or_create_player, get_player, set_player_room
from state.queues import join_queue, find_match, is_in_queue
from state.cleanup import cleanup_stale_rooms
from telegram_pkg import keyboards
from telegram_pkg.callback_parser import parse_callback, matrix_to_edge_id
from timers.turn_timer import handle_timeout


def room(mode=GameMode.PVP_FRIEND, size=3):
    for uid in (1, 2, 3):
        get_or_create_player(uid, f'test{uid}', f'Test {uid}')
    r = create_room(mode, size, 1, None if mode == GameMode.PVE else 2,
                    bot_difficulty='medium', theme='night')
    r.start_game()
    set_player_room(1, r.id)
    if r.player_b_id:
        set_player_room(2, r.id)
    return r


def wire(r, raw):
    # Baseline uses legacy keyboards; patched code binds the same button to a room/version.
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('test', callback_data=raw)]])
    binder = getattr(keyboards, 'bind_game_keyboard', lambda k, _: k)
    return binder(keyboard, r).inline_keyboard[0][0].callback_data


def occupied(r):
    return sum(e.is_occupied for e in r.board.edges.values())


def fake_render(monkeypatch):
    async def nothing(*args, **kwargs):
        pass
    monkeypatch.setattr(game, 'send_game_state', nothing)
    monkeypatch.setattr(game, 'send_game_state_new_message', nothing)


@pytest.mark.asyncio
async def test_leave_releases_both_players(transport):
    ctx, update = transport
    r = room()
    await game.game_callback(update(1, wire(r, 'leave')), ctx)
    assert get_player(1).current_room_id is None
    assert get_player(2).current_room_id is None
    assert get_room(r.id) is None


@pytest.mark.asyncio
async def test_finished_game_can_rematch(transport):
    ctx, update = transport
    r = room(GameMode.PVE)
    r.complete_game()
    await game.send_game_over(update(), ctx, r)
    assert get_player(1).current_room_id == r.id
    await game.game_callback(update(1, wire(r, 'rm')), ctx)
    new = get_room(get_player(1).current_room_id)
    assert new and new.id != r.id and new.state == RoomState.ACTIVE
    assert new.theme == 'night'
    assert new.bot_difficulty == 'medium'
    assert get_room(r.id) is None


@pytest.mark.asyncio
async def test_world_pvp_sends_board_to_both(transport):
    ctx, update = transport
    for uid in (1, 2):
        get_or_create_player(uid, '', 'Test')
    await play.start_pvp_game(update(2), ctx, 1, 2, 3)
    assert {c.kwargs['chat_id'] for c in ctx.bot.send_photo.call_args_list} == {1, 2}


@pytest.mark.parametrize('size', [3, 10304, 10305, 10404, 10505, 10606])
def test_world_queue_supports_offered_sizes(size):
    assert join_queue(1, size)
    assert join_queue(2, size)
    assert find_match(size) == (1, 2)


def test_cleanup_does_not_clear_newer_match():
    old = room()
    old.complete_game()
    old.completed_at = datetime.now() - timedelta(minutes=6)
    new = room(GameMode.PVE)
    assert cleanup_stale_rooms() == 1
    assert get_player(1).current_room_id == new.id


@pytest.mark.asyncio
async def test_stale_button_after_two_turns(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room()
    stale = wire(r, 'e:h:0:5')
    await game.game_callback(update(1, wire(r, 'e:h:0:1')), ctx)
    await game.game_callback(update(2, wire(r, 'e:h:0:3')), ctx)
    await game.game_callback(update(1, stale), ctx)
    assert occupied(r) == 2


@pytest.mark.asyncio
async def test_concurrent_different_buttons_apply_once(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room()
    gate = asyncio.Event()
    a, b = update(1, wire(r, 'e:h:0:1')), update(1, wire(r, 'e:h:0:3'))
    async def delayed_ack(*args, **kwargs):
        gate.set()
        await asyncio.sleep(0)
    a.callback_query.answer.side_effect = delayed_ack
    await asyncio.gather(game.game_callback(a, ctx), game.game_callback(b, ctx))
    assert occupied(r) == 1
    assert r.current_player_index == 1


@pytest.mark.asyncio
async def test_old_room_button_cannot_affect_new_room(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    old = room()
    stale = wire(old, 'e:h:0:1')
    new = room()
    await game.game_callback(update(1, stale), ctx)
    assert occupied(new) == 0


@pytest.mark.asyncio
async def test_out_of_turn_and_non_member(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room()
    set_player_room(3, r.id)
    await game.game_callback(update(2, wire(r, 'e:h:0:1')), ctx)
    await game.game_callback(update(3, wire(r, 'e:h:0:1')), ctx)
    assert occupied(r) == 0


@pytest.mark.asyncio
async def test_numbered_double_click(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room(size=10505)
    data = wire(r, 'num:1')
    await asyncio.gather(*(game.game_callback(update(1, data), ctx) for _ in range(2)))
    assert occupied(r) == 1 and r.current_player_index == 1


@pytest.mark.asyncio
async def test_malformed_coordinates_are_rejected(transport):
    ctx, update = transport
    r = room()
    for raw in ('e:h:bad:1', 'e:x:0:1', 'e:h:1:0', 'e:h:-2:1', 'e:v:1:999'):
        await game.game_callback(update(1, wire(r, raw)), ctx)
    assert occupied(r) == 0


def test_turn_core_capture_one_and_extra_turn():
    board = Board(2, 1)
    for eid in ('h_0_0', 'h_1_0', 'v_0_0'):
        board.place_edge(eid, '2')
    result = apply_turn(board, '1', 'v_0_1', '1', '2')
    assert result.success and result.extra_turn and result.captures == [(0, 0)]
    assert result.next_player == '1' and not result.game_over
    assert apply_turn(board, '1', 'v_0_1', '1', '2').error == TurnError.EDGE_OCCUPIED


def test_turn_core_capture_two_and_winner():
    board = Board(2, 1)
    for eid in board.edges:
        if eid != 'v_0_1':
            board.place_edge(eid, '2')
    result = apply_turn(board, '1', 'v_0_1', '1', '2')
    assert result.success and len(result.captures) == 2 and result.game_over
    score = calculate_result(board, '1', '2')
    assert score.winner_id == '1' and score.player_a_score == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('difficulty', ['easy', 'medium', 'hard'])
async def test_full_pve_match_each_difficulty(difficulty, transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room(GameMode.PVE)
    r.bot_difficulty = difficulty
    # Deterministic AI RNG, real bot strategies and handler loop.
    import random
    random.seed(41)
    for _ in range(r.board.total_edges):
        if r.state != RoomState.ACTIVE:
            break
        assert r.current_player_index == 0
        edge = r.board.get_available_edges()[0]
        orientation, row, col = edge.split('_')
        row, col = int(row), int(col)
        raw = f'e:{orientation}:{2*row + (orientation == "v")}:{2*col + (orientation == "h")}'
        await game.game_callback(update(1, wire(r, raw)), ctx)
    assert r.state == RoomState.COMPLETED and r.board.is_game_over()
    assert count_player_squares(r.board, '1') + count_player_squares(r.board, 'bot') == 9


@pytest.mark.asyncio
async def test_friend_invite_and_full_pvp(transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Test')
    r = create_room(GameMode.PVP_FRIEND, 3, 1)
    set_player_room(1, r.id)
    await start.handle_invite_join(update(2), ctx, r.invite_code)
    assert r.state == RoomState.ACTIVE and r.player_b_id == 2
    for _ in range(r.board.total_edges):
        eid = r.board.get_available_edges()[0]
        o, row, col = eid.split('_')
        data = f'e:{o}:{2*int(row)+(o=="v")}:{2*int(col)+(o=="h")}'
        await game.game_callback(update(r.current_player_id, wire(r, data)), ctx)
    assert r.state == RoomState.COMPLETED
    assert sum(s.owner is not None for row in r.board.squares for s in row) == 9


@pytest.mark.parametrize('size', [10404, 10505, 10606])
def test_pagination_covers_all_edges(size):
    r = room(size=size)
    seen = set()
    for page in range(2):
        keyboard = keyboards.lines_keyboard(r.board, '1', '2', page)
        assert all(len(row) <= 8 for row in keyboard.inline_keyboard)
        assert sum(map(len, keyboard.inline_keyboard)) < 100
        for row in keyboard.inline_keyboard:
            for button in row:
                cb = parse_callback(button.callback_data)
                assert len(button.callback_data.encode()) <= 64
                if cb.is_edge:
                    seen.add(matrix_to_edge_id(cb.edge_type, cb.edge_matrix_row, cb.edge_matrix_col))
    assert seen == set(r.board.edges)


@pytest.mark.asyncio
@pytest.mark.parametrize('response', ['yes', 'no'])
async def test_pvp_rematch_response_and_replay(response, transport):
    ctx, update = transport
    r = room()
    r.complete_game()
    await game.send_game_over(update(), ctx, r)
    await game.game_callback(update(1, wire(r, 'rm')), ctx)
    data = wire(r, f'rm:{response}')
    await game.game_callback(update(2, data), ctx)
    if response == 'yes':
        new = get_room(get_player(1).current_room_id)
        assert new and new.id != r.id and new.theme == r.theme
        assert get_player(2).current_room_id == new.id
    else:
        assert get_player(1).current_room_id is None
        assert get_player(2).current_room_id is None
    assert get_room(r.id) is None
    count = len(get_all_rooms())
    await game.game_callback(update(2, data), ctx)
    assert len(get_all_rooms()) == count


@pytest.mark.asyncio
async def test_requester_cannot_accept_own_rematch(transport):
    ctx, update = transport
    r = room()
    r.complete_game()
    await game.game_callback(update(1, wire(r, 'rm')), ctx)
    await game.game_callback(update(1, wire(r, 'rm:yes')), ctx)
    assert get_room(r.id) is r and r.state == RoomState.COMPLETED


@pytest.mark.asyncio
async def test_rematch_cannot_pull_opponent_from_new_match(transport):
    ctx, update = transport
    old = room()
    old.complete_game()
    await game.game_callback(update(1, wire(old, 'rm')), ctx)
    await play.handle_difficulty_selection(update(1), ctx, 'easy')
    new_id = get_player(1).current_room_id
    assert new_id != old.id
    await game.game_callback(update(2, wire(old, 'rm:yes')), ctx)
    assert get_player(1).current_room_id == new_id
    assert len(get_all_rooms()) == 2


@pytest.mark.asyncio
async def test_capture_rejects_second_old_button_even_with_extra_turn(transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    r = room()
    for eid in ('h_0_0', 'h_1_0', 'v_0_0'):
        r.board.place_edge(eid, '2')
    capture, stale = wire(r, 'e:v:1:2'), wire(r, 'e:h:0:3')
    await game.game_callback(update(1, capture), ctx)
    assert r.current_player_id == 1
    assert r.board.get_square(0, 0).owner == '1'
    await game.game_callback(update(1, stale), ctx)
    await game.game_callback(update(1, capture), ctx)
    assert occupied(r) == 4
    await game.game_callback(update(1, wire(r, 'e:h:0:3')), ctx)
    assert occupied(r) == 5 and r.current_player_id == 2


def test_stale_duplicate_early_and_terminal_timers():
    r = room()
    version = r.state_version
    assert handle_timeout(r, version) is False  # not due
    assert r.consecutive_timeouts_a == 0
    r.switch_player()
    r.turn_started_at = datetime.now() - timedelta(seconds=46)
    assert handle_timeout(r, version) is False  # previous turn
    assert r.consecutive_timeouts_b == 0
    current = r.state_version
    handle_timeout(r, current)
    handle_timeout(r, current)
    assert r.consecutive_timeouts_b == 1  # duplicate delivery
    r.complete_game()
    assert handle_timeout(r, current) is False
    assert r.consecutive_timeouts_b == 1


@pytest.mark.asyncio
async def test_page_bounds_and_stale_page(transport):
    ctx, update = transport
    r = room(size=10606)
    for value in ('-1', '99', 'bad'):
        await game.game_callback(update(1, wire(r, f'pg:{value}')), ctx)
        assert r.current_page == 0
    before = occupied(r)
    old = wire(r, 'pg:1')
    await game.game_callback(update(1, wire(r, 'e:h:0:1')), ctx)
    await game.game_callback(update(1, old), ctx)
    assert r.current_page == 0
    version = r.state_version
    await game.game_callback(update(2, wire(r, 'pg:1')), ctx)
    assert r.current_page == 1 and r.state_version == version
    assert occupied(r) == before + 1


@pytest.mark.asyncio
async def test_pending_invite_cancel_and_expiry(transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Test')
    await play.create_friend_invite(update(1), ctx, 3)
    r = get_room(get_player(1).current_room_id)
    code = r.invite_code
    await game.game_callback(update(1, wire(r, 'leave')), ctx)
    assert get_room_by_invite(code) is None
    await play.create_friend_invite(update(1), ctx, 3)
    r = get_room(get_player(1).current_room_id)
    r.created_at = datetime.now() - timedelta(minutes=11)
    await start.handle_invite_join(update(2), ctx, r.invite_code)
    assert get_room(r.id) is None
    assert get_player(1).current_room_id is None
    assert get_player(2) is None


@pytest.mark.asyncio
async def test_no_second_match_and_invite_replay(transport):
    ctx, update = transport
    r = room()
    await play.handle_difficulty_selection(update(1), ctx, 'hard')
    assert get_player(1).current_room_id == r.id
    assert len(get_all_rooms()) == 1
    await start.handle_invite_join(update(3), ctx, r.invite_code)
    assert r.player_b_id == 2


@pytest.mark.asyncio
async def test_start_resumes_same_board(transport):
    ctx, update = transport
    r = room()
    r.apply_move('1', 'h_0_0')
    await start.start_command(update(1), ctx)
    assert get_player(1).current_room_id == r.id and occupied(r) == 1
    assert ctx.bot.send_photo.await_count == 1


@pytest.mark.asyncio
async def test_start_can_cancel_pending_invite(transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Test')
    await play.create_friend_invite(update(1), ctx, 3)
    u = update(1)
    await start.start_command(u, ctx)
    keyboard = u.message.reply_text.call_args.kwargs['reply_markup']
    assert any(b.callback_data.startswith('leave:') for row in keyboard.inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_start_recovers_interrupted_bot_turn(transport):
    ctx, update = transport
    r = room(GameMode.PVE)
    r.apply_move('1', 'h_0_0')  # e.g. I/O interrupted after committing the human move
    assert r.current_player_index == 1
    u = update(1)
    u.callback_query = None
    await start.start_command(u, ctx)
    assert r.state == RoomState.COMPLETED or r.current_player_index == 0
    assert occupied(r) >= 2


@pytest.mark.asyncio
async def test_failed_delivery_does_not_allow_duplicate_move(transport):
    from telegram.error import NetworkError
    ctx, update = transport
    r = room()
    data = wire(r, 'e:h:0:1')
    ctx.bot.send_photo.side_effect = NetworkError('offline delivery failure')
    with pytest.raises(NetworkError):
        await game.game_callback(update(1, data), ctx)
    assert occupied(r) == 1 and r.current_player_id == 2
    await game.game_callback(update(1, data), ctx)
    assert occupied(r) == 1


@pytest.mark.asyncio
async def test_failed_ack_does_not_strand_pve(transport):
    from telegram.error import BadRequest
    ctx, update = transport
    r = room(GameMode.PVE)
    u = update(1, wire(r, 'e:h:0:1'))
    u.callback_query.answer.side_effect = BadRequest('Query is too old')
    await game.game_callback(u, ctx)
    assert r.current_player_index == 0 or r.state == RoomState.COMPLETED


@pytest.mark.asyncio
async def test_afk_unavailable_does_not_change_match(transport):
    ctx, update = transport
    r = room()
    for raw in ('afk:bot', 'afk:surrender'):
        await game.game_callback(update(1, wire(r, raw)), ctx)
    assert r.state == RoomState.ACTIVE and occupied(r) == 0
    assert all(not b.callback_data.startswith('afk:') for row in keyboards.afk_choice_keyboard().inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_legacy_buttons_fail_closed(transport):
    ctx, update = transport
    r = room()
    for raw in ('e:h:0:1', 'num:1', 'pg:1', 'rm', 'leave', 'afk:bot'):
        await game.game_callback(update(1, raw), ctx)
    assert get_room(r.id) is r and occupied(r) == 0


@pytest.mark.parametrize('size', [3, 10304, 10305, 10404, 10505, 10606])
@pytest.mark.parametrize('theme', ['classic', 'forest', 'night'])
def test_rendered_board_and_callbacks(size, theme):
    from io import BytesIO
    from PIL import Image
    from render.board_renderer import render_board
    r = room(size=size)
    image = render_board(r.board, theme_name=theme, player_a_id='1', player_b_id='2',
                         show_numbers=r.input_mode in ('numbered', 'lines'))
    with Image.open(BytesIO(image)) as img:
        img.verify()
    if r.input_mode == 'classic':
        k = keyboards.game_board_keyboard(r.board, '1', '2')
    elif r.input_mode == 'numbered':
        k = keyboards.numbered_edge_keyboard(r.board)
    else:
        k = keyboards.lines_keyboard(r.board, '1', '2')
    k = keyboards.bind_game_keyboard(k, r)
    if r.input_mode == 'classic':
        # Preserve v1.5's grid, including its existing 9-column 4x4 layout.
        assert all(len(row) == 2 * r.board.width + 1 for row in k.inline_keyboard[:-1])
    else:
        assert all(len(row) <= 8 for row in k.inline_keyboard)
    assert sum(map(len, k.inline_keyboard)) <= 100
    for row in k.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode()) <= 64
            if button.callback_data.startswith(('e:', 'num:', 'leave:', 'pg:')):
                cb = parse_callback(button.callback_data)
                assert cb.room_id == r.id and cb.version == r.state_version


def test_queue_cancel_is_routed():
    import ast
    import re
    from pathlib import Path
    tree = ast.parse(Path('bot/main.py').read_text())
    patterns = [kw.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'CallbackQueryHandler'
                for kw in node.keywords if kw.arg == 'pattern']
    assert any(re.match(pattern, 'cq') for pattern in patterns)


@pytest.mark.asyncio
@pytest.mark.parametrize('size', [3, 10304, 10305, 10404, 10505, 10606])
async def test_complete_world_pvp_sizes(size, transport, monkeypatch):
    ctx, update = transport
    fake_render(monkeypatch)
    # Exercise actual queue -> room start -> handler -> completion.
    assert join_queue(1, size) and join_queue(2, size)
    a, b = find_match(size)
    await play.start_pvp_game(update(2), ctx, a, b, size)
    r = get_room(get_player(1).current_room_id)
    for _ in range(r.board.total_edges):
        edge_number = __import__('game.edge_numbering', fromlist=['get_number_for_edge']).get_number_for_edge(r.board, r.board.get_available_edges()[0])
        await game.game_callback(update(r.current_player_id, wire(r, f'num:{edge_number}')), ctx)
    assert r.state == RoomState.COMPLETED and r.board.is_game_over()
    score = calculate_result(r.board, '1', '2')
    assert score.player_a_score + score.player_b_score == r.board.total_squares


@pytest.mark.asyncio
async def test_leave_notification_cannot_clear_replacement_room(transport):
    ctx, update = transport
    old = room()
    replacement = None
    async def notify(**kwargs):
        nonlocal replacement
        if kwargs['chat_id'] == 2:
            replacement = room(GameMode.PVE)
    ctx.bot.send_message.side_effect = notify
    await game.game_callback(update(1, wire(old, 'leave')), ctx)
    assert replacement is not None
    assert get_player(1).current_room_id == replacement.id


@pytest.mark.asyncio
async def test_start_restores_finished_result_after_delivery_failure(transport):
    ctx, update = transport
    r = room(GameMode.PVE)
    r.complete_game()
    u = update(1)
    u.callback_query = None
    await start.start_command(u, ctx)
    assert ctx.bot.send_photo.await_count == 1
    keyboard = ctx.bot.send_photo.call_args.kwargs['reply_markup']
    assert any(b.callback_data and b.callback_data.startswith('rm:') for row in keyboard.inline_keyboard for b in row)
