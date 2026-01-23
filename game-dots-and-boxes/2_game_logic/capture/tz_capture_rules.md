# TZ: Capture Rules

## Goal
Define how square completion is detected and captured.

## Inputs
- Edge placement location.
- Board state.

## Outputs
- List of squares captured by current move.

## Internal logic
- Check only squares adjacent to placed edge.

## Definition of Done (DoD)
- Captures are accurate and deterministic.
- Supports 0, 1, or 2 captures per move.

## Negative cases
- Capturing a square with only 3 edges.

## Edge cases
- Edge lies between two squares (both may capture).

---

## Capture Detection (Pseudo)
- For the placed edge, find adjacent square(s).
- For each adjacent square, verify all 4 edges occupied.
- If yes, mark as captured by current player.
