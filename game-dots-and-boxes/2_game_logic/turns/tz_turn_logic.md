# TZ: Turn Logic

## Goal
Define turn order, edge placement, and extra-turn rules.

## Inputs
- Current player ID.
- Edge placement request.
- Capture results.

## Outputs
- Updated turn state and next player.

## Internal logic
- Validate edge is empty.
- Apply edge; check capture; assign next turn.

## Definition of Done (DoD)
- Turn logic is deterministic.
- Extra turns are granted only on capture.

## Negative cases
- Allowing a player to move twice without capture.
- Placing an edge that is already occupied.

## Edge cases
- Move captures two squares (extra turn still single continuation).

---

## Turn Flow (Pseudo)
1. Validate edge availability.
2. Apply edge for current player.
3. Compute captures for affected squares.
4. If captures > 0: same player keeps turn.
5. Else: switch to opponent.
