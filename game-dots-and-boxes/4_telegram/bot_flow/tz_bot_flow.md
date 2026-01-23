# TZ: Bot Flow

## Goal
Define end-to-end Telegram bot user flow.

## Inputs
- Menu structure and modes.

## Outputs
- State machine for bot interactions.

## Internal logic
- Map user state to next screen and keyboard.

## Definition of Done (DoD)
- Flow covers onboarding, play, settings, and post-game.

## Negative cases
- User stuck without navigation.

## Edge cases
- Returning user with active game.

---

## Flow Summary
- /start -> Main Menu
- Play -> choose mode -> match setup -> game screen
- Game end -> results -> rematch or menu
