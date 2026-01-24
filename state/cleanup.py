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
WAITING_ROOM_TIMEOUT = timedelta(minutes=10)  # Waiting rooms expire after 10 min
FINISHED_ROOM_TIMEOUT = timedelta(minutes=5)  # Finished rooms cleaned after 5 min
ABORTED_ROOM_TIMEOUT = timedelta(minutes=5)  # Aborted rooms cleaned after 5 min
ACTIVE_ROOM_IDLE_TIMEOUT = timedelta(minutes=30)  # Active rooms idle cleanup


def cleanup_stale_rooms() -> int:
    """
    Remove stale rooms from memory.
    
    Returns number of rooms cleaned up.
    """
    now = datetime.now()
    cleaned = 0
    
    for room in get_all_rooms():
        should_delete = False
        
        # Check waiting rooms that timed out
        if room.state in {RoomState.CREATED, RoomState.WAITING}:
            if now - room.created_at > WAITING_ROOM_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up pre-game room {room.id} (timeout)")

        # Check idle active rooms
        elif room.state == RoomState.ACTIVE:
            if now - room.last_activity_at > ACTIVE_ROOM_IDLE_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up idle active room {room.id}")
        
        # Check finished rooms
        elif room.state == RoomState.FINISHED:
            if room.completed_at and now - room.completed_at > FINISHED_ROOM_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up finished room {room.id}")
        
        # Check aborted rooms
        elif room.state == RoomState.ABORTED:
            if room.completed_at and now - room.completed_at > ABORTED_ROOM_TIMEOUT:
                should_delete = True
                logger.info(f"Cleaning up aborted room {room.id}")
        
        if should_delete:
            # Release players from room
            set_player_room(room.player_a_id, None)
            if room.player_b_id:
                set_player_room(room.player_b_id, None)
            
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
