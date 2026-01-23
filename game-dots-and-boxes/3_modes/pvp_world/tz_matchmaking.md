# TZ: PvP World Matchmaking

## Goal
Define fast matchmaking flow and rating preparation.

## Inputs
- Queue requests.
- Player preferences (board size).

## Outputs
- Match creation or queue status.

## Internal logic
- Use FIFO or skill-based matching (design only).

## Definition of Done (DoD)
- Matchmaking states defined.
- Rating system is designed but not implemented.

## Negative cases
- Long waits without feedback.

## Edge cases
- Odd number of players in queue.

---

## Matchmaking Preferences
- Board size is **selected by the user before queueing**.
- Supported sizes: **3x3, 4x4, 5x5** squares.

## Rating Design (Plan Only)
- Record outcomes for future rating computation.
- Store minimal event logs for v2 migration.
