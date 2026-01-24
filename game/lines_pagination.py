"""
Pagination helpers for line-based keyboards.
"""

from __future__ import annotations

from typing import Iterable

from game.board import Board


MAX_BUTTONS_PER_PAGE = 60
MAX_COLUMNS_PER_ROW = 8


def _chunk_lengths(total: int, chunk_size: int) -> Iterable[int]:
    remaining = total
    while remaining > 0:
        size = min(chunk_size, remaining)
        yield size
        remaining -= size


def _iter_row_lengths(board: Board) -> Iterable[int]:
    for row in range(board.height + 1):
        yield from _chunk_lengths(board.width, MAX_COLUMNS_PER_ROW)
        if row < board.height:
            yield from _chunk_lengths(board.width + 1, MAX_COLUMNS_PER_ROW)


def get_lines_max_page(board: Board) -> int:
    """Return the max valid page index for line-based keyboards."""
    pages = 0
    current_buttons = 0

    for row_len in _iter_row_lengths(board):
        if current_buttons + row_len > MAX_BUTTONS_PER_PAGE:
            pages += 1
            current_buttons = 0
        current_buttons += row_len

    if current_buttons > 0:
        pages += 1

    return max(pages - 1, 0)
