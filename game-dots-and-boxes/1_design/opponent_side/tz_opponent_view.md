# TZ: Opponent View Rendering

## Goal
Define how the opponent’s identity and view should be rendered per player.

## Inputs
- Emoji identity rules.
- Board rendering output.

## Outputs
- Per-player rendering rules and metadata.

## Internal logic
- Renderer receives viewer context and game state.

## Definition of Done (DoD)
- Opponent emoji is correctly resolved per viewer.
- No global overwrites of emoji.

## Negative cases
- A shared image used for both players when emojis collide.

## Edge cases
- One player missing profile emoji (use default).

---

## Rendering Guidance
- Renderer is called with `viewer_id` and `game_state`.
- Captured squares use `viewer_specific_emoji_map`.
- If both players chose the same emoji, the renderer maps:
  - viewer -> chosen emoji
  - opponent -> fallback emoji
