# TZ: Player-Side Buttons

## Goal
Specify all player-facing buttons and their behaviors during gameplay and menus.

## Inputs
- Menu structure requirements.
- Inline keyboard constraints.

## Outputs
- Button list with labels, states, and actions.

## Internal logic
- Define buttons per screen and per state.
- Map each button to callback intent.

## Definition of Done (DoD)
- Every screen has an explicit button set.
- Buttons are deterministic for a given state.

## Negative cases
- Missing button for required flow (e.g., rematch accept/decline).
- Buttons that require free-text input.

## Edge cases
- Timer expiry while a button is shown.
- Same emoji rendering per viewer.

---

## Button Inventory (High-Level)
- **Main Menu**: Play, Profile, Settings, Support Project.
- **Play Menu**: PvE, PvP World, PvP Friend.
- **PvP Friend**: Create Invite, Enter Code, Back.
- **Profile**: View stats, Change emoji, Back.
- **Settings**: Change emoji, Edge color preset, Visual prefs, Back.
- **Game Board**: Inline keyboard grid representing edges.
- **Post-Game**: Rematch, Back to Menu, Share (optional if supported).
- **AFK Prompt**: Continue vs Bot, Surrender.

## Callback Mapping (Conceptual)
- Buttons map to short action identifiers (e.g., `play_pve`, `settings_colors`).
- Game board edges map to `edge:<id>`.
