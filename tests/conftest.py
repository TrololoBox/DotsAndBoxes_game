import os
import socket
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

os.environ['BOT_TOKEN'] = '123456789:OFFLINE_TEST_TOKEN_DO_NOT_USE'


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    from state.cleanup import cleanup_all
    def denied(*args, **kwargs):
        raise AssertionError('Network forbidden in offline regression tests')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)
    cleanup_all()
    yield
    cleanup_all()


@pytest.fixture
def transport():
    counter = iter(range(100, 10000))
    async def sent(**kwargs):
        return SimpleNamespace(message_id=next(counter))
    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=sent),
        send_message=AsyncMock(side_effect=sent),
        edit_message_media=AsyncMock(),
        get_me=AsyncMock(return_value=SimpleNamespace(username='offline_test_bot')),
    )
    context = SimpleNamespace(bot=bot, user_data={}, args=[])
    def update(uid=1, data='noop:dot'):
        user = SimpleNamespace(id=uid, username=f'test{uid}', first_name=f'Test {uid}')
        message = SimpleNamespace(delete=AsyncMock(), reply_text=AsyncMock())
        query = SimpleNamespace(data=data, answer=AsyncMock(), message=message,
                                edit_message_caption=AsyncMock(), edit_message_text=AsyncMock())
        return SimpleNamespace(effective_user=user, callback_query=query, message=message)
    return context, update
