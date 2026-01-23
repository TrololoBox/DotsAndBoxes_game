# TZ: Inline Keyboard

## Goal
Define keyboard layout standards for all screens.

## Inputs
- Board size and state.

## Outputs
- Keyboard matrix definitions.

## Internal logic
- Each edge maps to a button with a stable callback id.

## Definition of Done (DoD)
- Keyboard layout matches board geometry.
- Non-interactive dots are not buttons.

## Negative cases
- Dots represented as clickable buttons.

## Edge cases
- Large board causing Telegram max button limits.

---

## Board Keyboard Rules
- Edges are buttons; dots are rendered only in image.
- Occupied edges show alternative marker symbol.
- Buttons for occupied edges are disabled (no-op callbacks).
