# Vision

## Goal
Define the product vision, positioning, and non-negotiable constraints for the Dots and Boxes Telegram bot.

## Inputs
- Project overview and hard constraints.
- Target platform limitations (Telegram Bot API, inline keyboard only).
- Monetization rules.

## Outputs
- Clear product intent and scope boundaries.
- Shared understanding of what **must** be delivered in v1.
- Explicit exclusions to prevent scope creep.

## Internal logic
- Consolidate hard constraints into a single, human-readable vision statement.
- Identify scope boundaries (in/out) for v1.

## Definition of Done (DoD)
- Vision statement is concise and unambiguous.
- Must-have constraints are listed explicitly.
- Non-goals are documented.

## Negative cases
- Vision contradicts hard constraints.
- Vision implies unsupported features (e.g., WebApp, spectators).

## Edge cases
- None; this is a static document.

---

## Product Vision
“Dots and Boxes” is a fast, turn-based Telegram bot game that recreates the classic paper game using inline keyboards and generated images. The product prioritizes clarity, fairness, and accessibility while keeping setup friction minimal. The bot is the only interface: no WebApp, no external UI.

### In Scope (v1)
- PvE with three difficulty levels.
- PvP matchmaking and friend invites.
- Custom player emojis and edge color preferences.
- Turn timers and AFK handling with warm UX.
- In-memory runtime state only.
- Board rendering via Python Pillow.

### Out of Scope (v1)
- Spectator mode.
- Persistent storage of game sessions after restart.
- Ratings implementation (design only).
- Pay-to-win or forced ads.
