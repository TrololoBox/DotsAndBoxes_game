# TZ: Turn Timers

## Goal
Define timer behavior for turns and AFK handling.

## Inputs
- Mode and timer settings.
- Turn start time.

## Outputs
- Timeout events and actions.

## Internal logic
- Timer starts at turn assignment.
- On expiry, skip turn and trigger AFK flow if needed.

## Definition of Done (DoD)
- Timer triggers are deterministic.
- AFK flow is invoked correctly.

## Negative cases
- Timer continues after game end.

## Edge cases
- Player returns after AFK prompt is shown.

---

## Turn Timers (Simplified)
- **PvE**: 60 seconds per turn.
- **PvP**: 45 seconds per turn.

## AFK Flow
- On timeout, the player’s turn is skipped.
- After **2 consecutive timeouts**, present choice:
  - Continue vs Bot
  - Surrender
- Copy must be warm and human.
