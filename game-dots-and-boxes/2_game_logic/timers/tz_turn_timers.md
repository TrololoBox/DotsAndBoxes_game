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

## AFK Flow
- On timeout, the player’s turn is skipped.
- If repeated or threshold exceeded, present choice:
  - Continue vs Bot
  - Surrender
- Copy must be warm and human.
