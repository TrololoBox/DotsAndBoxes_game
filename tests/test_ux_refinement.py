"""Player-visible fixes approved after the 30 October review."""
from datetime import datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from telegram.error import NetworkError, Forbidden, BadRequest

from bot.handlers import game, start, play
from game.edge_numbering import get_edge_numbers
from render.board_renderer import render_board
from state.players import get_or_create_player, get_player, set_player_room
from state.rooms import create_room, get_room, GameMode, RoomState
from state.queues import join_queue, is_in_queue
from telegram_pkg.callback_parser import parse_callback
from telegram_pkg.keyboards import numbered_edge_keyboard, lines_page_count
from test_player_ux import active_room, wire


@pytest.mark.parametrize('size', [3, 10304, 10305, 10404, 10505, 10606])
def test_every_number_keeps_its_cell_until_the_board_is_full(size):
    r = active_room(size)
    mapping = get_edge_numbers(r.board)
    originals = [numbered_edge_keyboard(r.board, page) for page in range(lines_page_count(r.board))]
    for edge_id, number in mapping.items():
        r.board.place_edge(edge_id, '1')
        for page, original in enumerate(originals):
            kb = numbered_edge_keyboard(r.board, page)
            assert [len(row) for row in kb.inline_keyboard] == [len(row) for row in original.inline_keyboard]
            for before_row, after_row in zip(original.inline_keyboard, kb.inline_keyboard):
                for before, after in zip(before_row, after_row):
                    cb = parse_callback(before.callback_data)
                    if cb.is_num:
                        occupied = cb.edge_number <= number
                        assert after.text == (f'{cb.edge_number}✓' if occupied else str(cb.edge_number))
                        after_cb = parse_callback(after.callback_data)
                        if occupied:
                            assert after_cb.noop_reason == 'occupied'
                        else:
                            assert after_cb.edge_number == cb.edge_number


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [NetworkError('temporary failure'), Forbidden('blocked')])
async def test_move_delivery_failure_does_not_hide_the_other_players_turn(error, transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    r.message_a_id, r.message_b_id = 10, 20
    stale_b = wire(r, 'num:2')
    async def edit(**kwargs):
        if kwargs['chat_id'] == 1:
            raise error
    ctx.bot.edit_message_media.side_effect = edit
    with pytest.raises(type(error)):
        await game.game_callback(update(1, wire(r, 'num:1')), ctx)
    assert [c.kwargs['chat_id'] for c in ctx.bot.edit_message_media.call_args_list] == [1, 2]
    assert r.current_player_id == 2
    version = r.state_version
    await game.game_callback(update(2, stale_b), ctx)
    assert ctx.bot.edit_message_media.call_args.kwargs['chat_id'] == 2
    assert r.state_version == version and not r.board.get_edge('h_0_1').is_occupied


@pytest.mark.asyncio
async def test_stale_tap_recovers_after_connection_returns_without_replaying_move(transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    r.message_a_id, r.message_b_id = 10, 20
    old = wire(r, 'num:1')
    ctx.bot.edit_message_media.side_effect = NetworkError('temporary failure')
    with pytest.raises(NetworkError):
        await game.game_callback(update(1, old), ctx)
    ctx.bot.edit_message_media.side_effect = None
    await game.game_callback(update(1, old), ctx)
    assert sum(e.is_occupied for e in r.board.edges.values()) == 1
    delivered = ctx.bot.edit_message_media.call_args.kwargs
    assert delivered['chat_id'] == 1
    callbacks = [parse_callback(b.callback_data) for row in delivered['reply_markup'].inline_keyboard for b in row]
    assert all(cb.version == r.state_version for cb in callbacks if cb.is_num)
    await game.game_callback(update(2, wire(r, 'num:2')), ctx)
    assert sum(e.is_occupied for e in r.board.edges.values()) == 2
    assert r.current_player_id == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['world_start', 'invite_join', 'rematch', 'result'])
async def test_other_pvp_recipient_is_attempted_for_every_lifecycle_screen(scenario, transport):
    ctx, update = transport
    first = 2 if scenario == 'invite_join' else 1
    sent = []
    async def send(**kwargs):
        sent.append(kwargs['chat_id'])
        if kwargs['chat_id'] == first:
            raise Forbidden('blocked')
        return SimpleNamespace(message_id=99)
    ctx.bot.send_photo.side_effect = send
    for uid in (1, 2):
        get_or_create_player(uid, '', 'Player')
    with pytest.raises(Forbidden):
        if scenario == 'world_start':
            await play.start_pvp_game(update(1), ctx, 1, 2, 3)
        elif scenario == 'invite_join':
            r = create_room(GameMode.PVP_FRIEND, 3, 1)
            set_player_room(1, r.id)
            await start.handle_invite_join(update(2), ctx, r.invite_code)
        else:
            r = active_room(mode=GameMode.PVP_FRIEND)
            r.complete_game()
            if scenario == 'rematch':
                await game._start_rematch_game(update(2), ctx, r)
            else:
                await game.send_game_over(update(1), ctx, r)
    assert sent == ([2, 1] if first == 2 else [1, 2])


@pytest.mark.asyncio
async def test_stale_ack_failure_still_refreshes_but_never_accepts_exit(transport):
    ctx, update = transport
    r = active_room(mode=GameMode.PVP_FRIEND)
    old_exit = wire(r, 'leave:yes')
    r.apply_move('1', 'h_0_0')
    u = update(1, old_exit)
    u.callback_query.answer.side_effect = BadRequest('Query is too old')
    await game.game_callback(u, ctx)
    assert get_room(r.id) is r
    assert ctx.bot.send_photo.await_count == 1


@pytest.mark.asyncio
async def test_old_match_and_outsider_cannot_refresh_someone_elses_board(transport):
    ctx, update = transport
    r = active_room()
    old = wire(r, 'num:1')
    other = active_room()
    await game.game_callback(update(1, old), ctx)
    await game.game_callback(update(2, wire(other, 'num:1')), ctx)
    ctx.bot.send_photo.assert_not_awaited()
    assert not any(e.is_occupied for e in r.board.edges.values())
    assert not any(e.is_occupied for e in other.board.edges.values())


@pytest.mark.asyncio
@pytest.mark.parametrize('route', ['menu', 'direct_resume', 'display'])
async def test_expired_invitation_cannot_be_redisplayed(route, transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Player')
    r = create_room(GameMode.PVP_FRIEND, 3, 1)
    set_player_room(1, r.id)
    r.created_at = datetime.now() - timedelta(minutes=11)
    u = update(1, 'menu:resume')
    if route == 'menu':
        await start.main_menu_callback(u, ctx)
    elif route == 'direct_resume':
        assert await start.resume_current_game(u, ctx) is False
    else:
        await play.show_friend_invite(u, ctx, r)
    assert get_room(r.id) is None and get_player(1).current_room_id is None
    assert all(r.invite_code not in str(c) for c in u.callback_query.edit_message_text.call_args_list)


@pytest.mark.asyncio
async def test_resumed_invitation_reports_remaining_lifetime_not_a_new_ten_minutes(transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Player')
    r = create_room(GameMode.PVP_FRIEND, 3, 1)
    set_player_room(1, r.id)
    r.created_at = datetime.now() - timedelta(minutes=9, seconds=30)
    u = update(1, 'menu:resume')
    await start.main_menu_callback(u, ctx)
    text = u.callback_query.edit_message_text.call_args.args[0]
    assert 'Осталось: 0:30' in text and '10 минут' not in text
    assert r.invite_code in text and get_room(r.id) is r


@pytest.mark.asyncio
async def test_search_remains_visible_in_menu_rules_return_and_can_be_cancelled(transport):
    ctx, update = transport
    get_or_create_player(1, '', 'Player')
    join_queue(1, 10304)
    await start.main_menu_callback(update(1, 'menu:rules'), ctx)
    u = update(1, 'menu:main')
    await start.main_menu_callback(u, ctx)
    text = u.callback_query.edit_message_text.call_args.args[0]
    kb = u.callback_query.edit_message_text.call_args.kwargs['reply_markup']
    assert '3×4' in text and 'Поиск продолжается' in text and 'Место в очереди: 1' in text
    assert any(b.callback_data == 'cq' for row in kb.inline_keyboard for b in row)
    assert is_in_queue(1)
    await play.play_callback(update(1, 'cq'), ctx)
    assert not is_in_queue(1)


@pytest.mark.asyncio
async def test_queued_quick_game_leaves_search_and_menu_shows_match(transport):
    ctx, update = transport
    join_queue(1, 3)
    await start.main_menu_callback(update(1, 'menu:quick'), ctx)
    u = update(1, 'menu:main')
    await start.main_menu_callback(u, ctx)
    assert not is_in_queue(1)
    kb = u.callback_query.edit_message_text.call_args.kwargs['reply_markup']
    assert any(b.callback_data == 'menu:resume' for row in kb.inline_keyboard for b in row)
    assert not any(b.callback_data == 'cq' for row in kb.inline_keyboard for b in row)


@pytest.mark.asyncio
async def test_start_command_also_shows_current_search(transport):
    ctx, update = transport
    join_queue(1, 10304)
    u = update(1)
    u.callback_query = None
    await start.start_command(u, ctx)
    call = u.message.reply_text.call_args
    assert 'Ищем соперника · 3×4' in call.args[0]
    assert any(b.callback_data == 'cq' for row in call.kwargs['reply_markup'].inline_keyboard for b in row)


@pytest.mark.parametrize('theme', ['classic', 'forest', 'night'])
def test_occupied_number_is_muted_and_last_number_has_a_font_independent_star(theme):
    from PIL import ImageFont
    r = active_room()
    edge = 'h_0_0'
    free = Image.open(BytesIO(render_board(r.board, theme, '1', 'bot', show_numbers=True))).convert('RGB')
    r.board.place_edge(edge, '1')
    taken = Image.open(BytesIO(render_board(r.board, theme, '1', 'bot', show_numbers=True))).convert('RGB')
    last = Image.open(BytesIO(render_board(r.board, theme, '1', 'bot', show_numbers=True, last_edge_id=edge))).convert('RGB')
    assert free.getpixel((80, 29)) != taken.getpixel((80, 29))
    # Star centre is inside the left extension of the final-move badge.
    draw = __import__('PIL.ImageDraw', fromlist=['Draw']).Draw(last)
    bounds = draw.textbbox((80, 40), '1', font=ImageFont.load_default(size=28), anchor='mm')
    star_center = (bounds[0] - 12, 40)
    assert last.getpixel(star_center) == (17, 17, 17)
    assert taken.getpixel(star_center) != (17, 17, 17)


def test_caption_shrinks_after_first_move_but_keeps_score_turn_and_last_line():
    r = active_room(mode=GameMode.PVP_FRIEND)
    first = game.game_caption(r, 1)
    assert 'Найди линию' in first and 'ещё ход' in first
    r.apply_move('1', 'h_0_0')
    later = game.game_caption(r, 1)
    assert len(later) < len(first) * .7
    assert 'Найди линию' not in later and '★' in later and '№1' in later
    assert 'Ход соперника' in later and '0</b>' in later
