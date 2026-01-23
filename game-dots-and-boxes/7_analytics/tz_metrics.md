# TZ: Analytics Metrics

## Goal
Define analytics events and data captured.

## Inputs
- Analytics requirements.

## Outputs
- Event list and fields.

## Internal logic
- Emit events on state transitions.

## Definition of Done (DoD)
- All major actions have events.

## Negative cases
- Missing events for game start/end.

## Edge cases
- Retry on failed analytics submission.

---

## Event List (Draft)
- `game_start` (mode, board_size, players)
- `game_end` (mode, duration, scores, winner)
- `edge_placed` (player, edge_id)
- `square_captured` (player, count)
- `turn_timeout` (player)
- `afk_choice` (choice)
- `donation_prompt_shown`
- `donation_clicked`
