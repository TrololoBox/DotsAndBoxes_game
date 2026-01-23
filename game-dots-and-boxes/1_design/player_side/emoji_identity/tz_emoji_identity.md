# TZ: Emoji Identity

## Goal
Define how player emoji selection, storage, and rendering should work.

## Inputs
- Hard identity rules.
- Settings menu.

## Outputs
- Emoji selection flow and rendering rules.

## Internal logic
- Store chosen emoji per user profile.
- During match rendering, resolve view-specific mapping.

## Definition of Done (DoD)
- Emoji selection is available in Settings.
- Emoji is immutable during a match.
- Rendering respects identical emoji rule.

## Negative cases
- Changing emoji mid-match.
- Same emoji displayed for both players to a single viewer.

## Edge cases
- Emoji not supported by client font.
- User chooses a multi-codepoint emoji.

---

## Emoji Rendering Rules
- Each user picks one emoji in Settings and stores it to their profile.
- In a game state, each viewer sees their own emoji for self.
- If both players picked the same emoji, the opponent is rendered with a **fallback emoji**.
- The fallback emoji is defined centrally (see open questions).
