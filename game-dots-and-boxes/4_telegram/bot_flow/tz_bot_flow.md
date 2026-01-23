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
- Play -> choose mode -> **choose board size** -> match setup -> game screen
- Game end -> results -> **soft-ad offer** -> rematch or menu

## Post-Match Soft-Ad Offer
- Show message with button: **"Посмотреть рекламу"**.
- On click, trigger ad playback (stub for now).

## Rematch Behavior
- Rematch restarts the same match configuration: same starting player, same board size, same colors, same emojis.
