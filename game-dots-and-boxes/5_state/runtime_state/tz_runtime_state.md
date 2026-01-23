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
- A user attempts to start a second game while one is active (must block).

---

## State Categories
- **Player Profile**: Telegram username, emoji, preferences.
- **Active Rooms**: players, board state, timers.
- **Queues**: matchmaking pools.

## Concurrency Rule
- Each user can have **only one active game** at a time.
