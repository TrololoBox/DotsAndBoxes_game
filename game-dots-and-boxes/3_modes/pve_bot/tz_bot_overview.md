# TZ: Bot Overview

## Goal
Define overall bot architecture, constraints, and shared behaviors.

## Inputs
- Game rules.
- Difficulty requirements.

## Outputs
- Shared bot interface and decision pipeline.

## Internal logic
- Bot consumes game state and returns chosen edge.

## Definition of Done (DoD)
- All difficulties follow same API.
- Bot never cheats (no hidden info).

## Negative cases
- Bot modifies game state directly.

## Edge cases
- Bot has no legal moves (game ended).

---

## Bot Interface
- Input: pure game state + difficulty.
- Output: chosen legal edge ID.
- Must respect current player and legal moves only.
