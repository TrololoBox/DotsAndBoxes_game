"""
Toast messages for invalid interactions.

All user feedback messages are defined here for consistency.
Tone: playful, warm, friendly. Messages are deterministic.
"""

TOAST_OCCUPIED_EDGE = "Сюда уже ходили 🙂 Попробуй другую грань."
TOAST_TAP_DOT = "Это точка 🙂 Здесь ходить нельзя."
TOAST_TAP_SQUARE = "Квадрат сам не сдаётся — замкни его гранями 😉"
TOAST_NOT_YOUR_TURN = "Сейчас не твой ход 🙂"
TOAST_GAME_FINISHED = "Игра уже закончена 🎉"
TOAST_TRANSITION_STATE = "Секундочку… мы сейчас решаем, что делать дальше 🤔"
TOAST_STALE_CALLBACK = "Клавиатура устарела. Откройте актуальное состояние."
TOAST_ROOM_NOT_FOUND = "Игра не найдена. Вернитесь в меню и начните заново."
TOAST_NOT_IN_ROOM = "Вы не участник этой игры."
TOAST_INVALID_NUMBER = "Неверный номер грани ❌"
TOAST_INVALID_EDGE = "Грань не найдена ❌"
TOAST_AD_PLACEHOLDER = "📺 Рекламный блок скоро появится!"
TOAST_INVALID_PAGE = "Эта страница больше недоступна."
TOAST_UNKNOWN_ERROR = "Что-то пошло не так 🤔"


# Public functions to get toast messages

def toast_occupied_edge() -> str:
    """Get toast for tapping an occupied edge."""
    return TOAST_OCCUPIED_EDGE


def toast_tap_dot() -> str:
    """Get toast for tapping a dot."""
    return TOAST_TAP_DOT


def toast_tap_square() -> str:
    """Get toast for tapping a square."""
    return TOAST_TAP_SQUARE


def toast_not_your_turn() -> str:
    """Get toast for tapping when it's not your turn."""
    return TOAST_NOT_YOUR_TURN


def toast_game_finished() -> str:
    """Get toast for tapping after game ended."""
    return TOAST_GAME_FINISHED


def toast_transition_state() -> str:
    """Get toast for tapping during transition/AFK state."""
    return TOAST_TRANSITION_STATE


def toast_stale_callback() -> str:
    """Get toast for stale callbacks."""
    return TOAST_STALE_CALLBACK


def toast_room_not_found() -> str:
    """Get toast for missing rooms."""
    return TOAST_ROOM_NOT_FOUND


def toast_not_in_room() -> str:
    """Get toast for non-participants."""
    return TOAST_NOT_IN_ROOM


def toast_invalid_number() -> str:
    """Get toast for invalid numbered input."""
    return TOAST_INVALID_NUMBER


def toast_invalid_edge() -> str:
    """Get toast for invalid edge input."""
    return TOAST_INVALID_EDGE


def toast_ad_placeholder() -> str:
    """Get toast for ad placeholder."""
    return TOAST_AD_PLACEHOLDER


def toast_invalid_page() -> str:
    """Get toast for invalid pagination."""
    return TOAST_INVALID_PAGE


def toast_unknown_error() -> str:
    """Get toast for unknown errors."""
    return TOAST_UNKNOWN_ERROR
