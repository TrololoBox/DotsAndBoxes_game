# TZ: Accessibility

## Goal
Ensure the board and controls are accessible and clearly distinguishable.

## Inputs
- Accessibility requirements from brief.

## Outputs
- Visual distinctions and alternative markers for occupied edges.

## Internal logic
- Specify rendering differences and keyboard markers.

## Definition of Done (DoD)
- Occupied edges are thicker than empty edges.
- Inline keyboard has an alternative marker for occupied edges.

## Negative cases
- Only color differentiates edges.
- No alternative symbol for occupied edges.

## Edge cases
- Small board sizes where thickness is hard to perceive.

---

## Requirements
- **Rendering**: occupied edges must be thicker or visually distinct (not just color).
- **Inline keyboard**: occupied edges must include a marker symbol.

## PROPOSAL
- Use a double-line visual (thicker stroke) for occupied edges in the PNG.
- For inline keyboard, use symbols:
  - empty edge: ⬜️
  - blue occupied: 🟦
  - red occupied: 🟥
  - additionally append a small marker such as “●” to occupied edges (e.g., 🟦●).
