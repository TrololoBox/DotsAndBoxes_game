"""
Matchmaking queues for PvP world matches.

FIFO matching by board size.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List


@dataclass
class QueueEntry:
    """Entry in the matchmaking queue."""
    telegram_id: int
    board_size: int
    joined_at: datetime
    
    def __hash__(self):
        return hash(self.telegram_id)


# Queues by board size
_queues: Dict[int, List[QueueEntry]] = {
    3: [],
    4: [],
    5: [],
    6: [],
    10304: [],
    10305: [],
    10404: [],
    10505: [],
    10606: [],
}


def join_queue(telegram_id: int, board_size: int) -> bool:
    """
    Add player to matchmaking queue.
    
    Returns True if added, False if already in queue.
    """
    if board_size not in _queues:
        return False
    
    # Check if already in any queue
    if is_in_queue(telegram_id):
        return False
    
    entry = QueueEntry(
        telegram_id=telegram_id,
        board_size=board_size,
        joined_at=datetime.now(),
    )
    _queues[board_size].append(entry)
    return True


def leave_queue(telegram_id: int) -> bool:
    """
    Remove player from any queue.
    
    Returns True if removed, False if not found.
    """
    for size, queue in _queues.items():
        for entry in queue:
            if entry.telegram_id == telegram_id:
                queue.remove(entry)
                return True
    return False


def is_in_queue(telegram_id: int) -> bool:
    """Check if player is in any queue."""
    for queue in _queues.values():
        for entry in queue:
            if entry.telegram_id == telegram_id:
                return True
    return False


def find_match(board_size: int) -> Optional[tuple[int, int]]:
    """
    Try to match two players in a queue.
    
    Returns tuple of (player_a_id, player_b_id) if match found, None otherwise.
    """
    if board_size not in _queues:
        return None
    
    queue = _queues[board_size]
    
    if len(queue) >= 2:
        # FIFO: match first two players
        player_a = queue.pop(0)
        player_b = queue.pop(0)
        return (player_a.telegram_id, player_b.telegram_id)
    
    return None


def get_queue_size(board_size: int) -> int:
    """Get number of players waiting in a queue."""
    return len(_queues.get(board_size, []))


def get_queue_position(telegram_id: int) -> Optional[int]:
    """Get player's position in queue (1-indexed)."""
    for queue in _queues.values():
        for i, entry in enumerate(queue):
            if entry.telegram_id == telegram_id:
                return i + 1
    return None


def get_queue_entry(telegram_id: int) -> Optional[QueueEntry]:
    """Return the current search so menus can show its real size and position."""
    return next((entry for queue in _queues.values() for entry in queue
                 if entry.telegram_id == telegram_id), None)


def clear_all_queues() -> None:
    """Clear all queues (for restart)."""
    for queue in _queues.values():
        queue.clear()
