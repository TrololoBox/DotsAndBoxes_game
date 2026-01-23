# TZ: Runtime State

## Goal
Define in-memory state structures and ownership boundaries.

## Inputs
- Game state requirements.
- Player profile requirements.

## Outputs
- State model (conceptual) and access patterns.

## Internal logic
- Separate game logic from storage.

## Definition of Done (DoD)
- Game state is pure and serializable in memory.
- Storage layer manages lifecycle only.

## Negative cases
- Logic layer directly manipulates storage.

## Edge cases
- Multiple concurrent games per user (open question).

---

## State Categories
- **Player Profile**: emoji, name, preferences.
- **Active Rooms**: players, board state, timers.
- **Queues**: matchmaking pools.
