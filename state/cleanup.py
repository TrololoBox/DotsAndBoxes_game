"""
Cleanup routines for stale state.

Handles abandoned rooms and periodic maintenance.
"""

from datetime import datetime, timedelta
import logging

from state.rooms import get_all_rooms, delete_room, RoomState
from state.players import set_player_room


logger = logging.getLogger(__name__)


# Cleanup thresholds
PENDING_ROOM_TIMEOUT = timedelta(minutes=10)  # Pending rooms expire after 10 min
COMPLETED_ROOM_TIMEOUT = timedelta(minutes=5)  # Completed rooms cleaned after 5 min


def cleanup_stale_rooms() -> int:
    """
    Remove stale rooms from memory.
    
    Returns number of rooms cleaned up.
    """
    now = datetime.now()
    cleaned = 0
    
    for room in get_all_rooms():
        should_delete = False
        
        # Check pending rooms that timed out
        if room.state == RoomState.PENDING:
            if now - room.created_at > PENDING_ROOM_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up pending room {room.id} (timeout)")
        
        # Check completed rooms
        elif room.state == RoomState.COMPLETED:
            if room.completed_at and now - room.completed_at > COMPLETED_ROOM_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up completed room {room.id}")
        
        # Check abandoned rooms
        elif room.state == RoomState.ABANDONED:
            should_delete = True
            logger.info(f"Cleaning up abandoned room {room.id}")
        
        if should_delete:
            delete_room(room.id)
            cleaned += 1
    
    return cleaned


def cleanup_all() -> None:
    """Full cleanup - run on server restart."""
    from state.rooms import clear_all_rooms
    from state.players import clear_all_players
    from state.queues import clear_all_queues
    
    clear_all_rooms()
    clear_all_players()
    clear_all_queues()
    
    logger.info("All state cleared")
