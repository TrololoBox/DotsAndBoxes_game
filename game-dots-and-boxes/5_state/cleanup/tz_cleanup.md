# TZ: Cleanup & Restart Behavior

## Goal
Define cleanup behavior for in-memory state and restart semantics.

## Inputs
- Runtime state.

## Outputs
- Cleanup policy.

## Internal logic
- On restart, clear all state.
- Periodic cleanup for abandoned rooms.

## Definition of Done (DoD)
- No stale rooms after restart.
- Abandoned rooms are removed.

## Negative cases
- Persisting rooms after restart.

## Edge cases
- Players mid-turn when cleanup occurs.

---

## Restart Rules
- All games cleared on server restart.
- All players released from rooms and queues.
