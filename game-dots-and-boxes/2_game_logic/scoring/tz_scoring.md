# TZ: Scoring

## Goal
Define scoring updates and winner resolution.

## Inputs
- Captured squares list.
- Current score.
- Game end status.

## Outputs
- Updated scores and winner (if ended).

## Internal logic
- Increment by number of captured squares.
- Compare scores at game end.

## Definition of Done (DoD)
- Score increments per square.
- Winner computed correctly.

## Negative cases
- Score increment per move rather than per square.

## Edge cases
- Tie game at end.

---

## Scoring Rules
- Each captured square = +1 to capturing player.
- Winner is higher score, tie yields draw.
