# TZ: Callback Data

## Goal
Define the callback data schema used by inline keyboards.

## Inputs
- Button intents.

## Outputs
- Callback format and validation rules.

## Internal logic
- Short, parseable identifiers.

## Definition of Done (DoD)
- All buttons map to a valid callback.
- Callback size fits Telegram limits.

## Negative cases
- Overly long callback strings.

## Edge cases
- Backwards compatibility for older callbacks.

---

## Callback Schema (Conceptual)
- `menu:<screen>`
- `play:<mode>`
- `edge:<edge_id>`
- `invite:<code>`
