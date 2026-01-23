# Game Rules

## Goal
Document immutable rules and game mechanics for developers and designers.

## Inputs
- Hard rules from project brief.

## Outputs
- Canonical rule set for gameplay logic and UI rendering.

## Internal logic
- Translate hard rules into explicit statements and constraints.

## Definition of Done (DoD)
- All rules are written as testable statements.
- No contradictions with the brief.

## Negative cases
- Missing rule for turn continuation after capture.
- Ambiguity in edge placement or scoring.

## Edge cases
- A single move capturing two squares.
- Same emoji chosen by both players (identity rendering).

---

## Canonical Rules
- The board is a grid of dots and edges surrounding square cells.
- A turn consists of placing exactly **one** edge.
- If the placed edge completes a square, the square is captured immediately.
- Captured squares show the capturer’s emoji and grant +1 score per square.
- Completing one or two squares grants an **extra turn** (repeat until no capture).
- The game ends when all edges are occupied.
- The winner is the player with the most captured squares.

## Identity Rendering Rule
If both players choose the same emoji:
- Each player views themselves using their chosen emoji.
- The opponent is displayed using a standard fallback emoji from the system.
- Rendering is per-viewer (not global).
