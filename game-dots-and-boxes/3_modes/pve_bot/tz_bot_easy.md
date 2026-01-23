# TZ: Bot Easy

## Goal
Specify easy bot behavior with intentional mistakes.

## Inputs
- Game state.

## Outputs
- A legal move, often suboptimal.

## Internal logic
- Prefer random edges.
- Occasionally complete a square if obvious.

## Definition of Done (DoD)
- Bot makes mistakes frequently.
- Still always chooses legal moves.

## Negative cases
- Bot always optimal.

## Edge cases
- Late-game board with few moves.

---

## Behavior Notes
- Weighted random move selection.
- Low probability to detect traps.
