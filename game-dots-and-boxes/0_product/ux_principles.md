# UX Principles

## Goal
Define experience principles for menus, in-game flow, and feedback.

## Inputs
- Platform constraints (inline keyboards only).
- Accessibility requirements.
- Monetization limitations.

## Outputs
- UX rules that guide copy, feedback, and interaction patterns.

## Internal logic
- Translate constraints into consistent UX behaviors.

## Definition of Done (DoD)
- Principles are actionable.
- Copy tone is specified where required.

## Negative cases
- Robotic or punitive messaging for AFK.
- UI elements that require WebApp capabilities.

## Edge cases
- Handling identical emojis.
- Re-rendering after timeouts.

---

## Principles
1. **Clarity first**: Every board state and button must be unambiguous.
2. **Human tone**: AFK and error messages are warm and supportive.
3. **Low friction**: Minimal steps to start a game.
4. **Accessibility**: Occupied edges are visually distinct (thicker) and have alternative symbols.
5. **Bot-only**: All interactions happen via inline keyboard and bot messages.
6. **Deterministic visuals**: Same state always produces the same image.
