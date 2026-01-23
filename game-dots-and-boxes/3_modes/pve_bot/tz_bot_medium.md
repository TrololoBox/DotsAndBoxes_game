# TZ: Bot Medium

## Goal
Specify medium bot behavior that avoids obvious traps.

## Inputs
- Game state.

## Outputs
- A legal move with basic heuristics.

## Internal logic
- Avoid moves that create a 3rd edge around a square for opponent.
- Prefer capturing squares when available.

## Definition of Done (DoD)
- Bot avoids obvious giveaways.
- Still not full chain calculation.

## Negative cases
- Bot ignores immediate captures.

## Edge cases
- Forced move that opens a square.

---

## Behavior Notes
- Simple heuristic evaluation per edge.
