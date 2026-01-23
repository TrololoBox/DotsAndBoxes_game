# TZ: Board Rendering (Python Pillow)

## Goal
Define deterministic board rendering using Python Pillow.

## Inputs
- Pure game state (grid size, edges, squares, player emojis).
- Viewer context for emoji mapping.
- Visual preferences (edge colors, theme).

## Outputs
- PNG image bytes representing the board.

## Internal logic
- Use PIL.Image, ImageDraw, and ImageFont.
- Draw layers in fixed order.

## Definition of Done (DoD)
- Same input state always yields identical PNG (deterministic).
- Output is a PNG image.
- Rendering uses only Pillow and standard libs.

## Negative cases
- Using non-Pillow rendering libraries.
- Renderer accessing runtime storage directly.

## Edge cases
- Very small or large board sizes.
- Missing emoji glyphs.

---

## Preset Themes (v1)
All color choices are presets only (no custom colors in v1).

- **Classic**: Player A `#2F80ED`, Player B `#EB5757`, Neutral `#BDBDBD`, Background `#F2F2F2`.
- **Forest**: Player A `#219653`, Player B `#F2994A`, Neutral `#BDBDBD`, Background `#F2F2F2`.
- **Night**: Player A `#56CCF2`, Player B `#BB6BD9`, Neutral `#4F4F4F`, Background `#1B1B1B`.

## Rendering Steps (Pseudo)
1. Create blank image with fixed background.
2. Draw dots at grid intersections.
3. Draw edges with thickness based on occupancy.
4. Draw square targets (neutral or captured).
5. Draw captured square emoji centered in square.
6. Return PNG bytes.

## Data Contract (Pure State)
- `board_width`, `board_height` in squares.
- `edges`: list or dict of edges with occupancy + owner.
- `squares`: list with captured owner or neutral.
- `player_emojis`: resolved map for viewer.
- `theme`: colors and sizes (from settings).
