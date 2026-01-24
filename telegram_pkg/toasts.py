"""
Toast messages for invalid interactions.

All user feedback messages are defined here for consistency.
Tone: playful, warm, friendly.
"""

import random
from typing import List


def _pick(messages: List[str]) -> str:
    """Pick a random message from list."""
    return random.choice(messages)


# Toast message lists for each scenario

TOAST_OCCUPIED_EDGE = [
    "Сюда уже ходили 🙂 Попробуй другую грань.",
    "Эта грань уже занята! Поле помнит всё 😄",
    "Поздно! Тут уже чей-то ход 👀",
]

TOAST_TAP_DOT = [
    "Это точка 🙂 Здесь ходить нельзя.",
    "Слишком точно! Но ходят по граням 😉",
]

TOAST_TAP_SQUARE = [
    "Квадрат сам не сдаётся — замкни его гранями 😉",
    "Почти! Сначала нужны рёбра.",
]

TOAST_NOT_YOUR_TURN = [
    "Подожди ход соперника ⏳",
    "Сейчас не твой ход 🙂",
]

TOAST_GAME_FINISHED = [
    "Игра уже закончена 🎉",
    "Этот матч уже в истории 🙂",
]

TOAST_TRANSITION_STATE = [
    "Секундочку… мы сейчас решаем, что делать дальше 🤔",
]


# Public functions to get toast messages

def toast_occupied_edge() -> str:
    """Get toast for tapping an occupied edge."""
    return _pick(TOAST_OCCUPIED_EDGE)


def toast_tap_dot() -> str:
    """Get toast for tapping a dot."""
    return _pick(TOAST_TAP_DOT)


def toast_tap_square() -> str:
    """Get toast for tapping a square."""
    return _pick(TOAST_TAP_SQUARE)


def toast_not_your_turn() -> str:
    """Get toast for tapping when it's not your turn."""
    return _pick(TOAST_NOT_YOUR_TURN)


def toast_game_finished() -> str:
    """Get toast for tapping after game ended."""
    return _pick(TOAST_GAME_FINISHED)


def toast_transition_state() -> str:
    """Get toast for tapping during transition/AFK state."""
    return _pick(TOAST_TRANSITION_STATE)
