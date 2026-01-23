# TZ: PvP Friend Invite Flow

## Goal
Define invite link and room code flow for friend matches.

## Inputs
- Player request to invite.
- Room code generation.

## Outputs
- Invite link/code and room state.

## Internal logic
- Create pending room with unique code.
- Join when second player accepts.

## Definition of Done (DoD)
- Invite flow described end-to-end.
- No spectators allowed.

## Negative cases
- Two players join the same invite simultaneously without safeguards.

## Edge cases
- Invite expires after timeout.

---

## Invite Options
- **Link**: deep-link to bot with payload code.
- **Code**: short code input via inline keyboard selections (no free-text).
