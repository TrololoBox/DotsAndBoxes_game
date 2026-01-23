# TZ: Room Lifecycle

## Goal
Define how rooms are created, managed, and destroyed in memory.

## Inputs
- Matchmaking requests.
- Friend invites.
- Runtime cleanup policy.

## Outputs
- Room lifecycle states and transitions.

## Internal logic
- Create room on match start.
- Destroy room on completion or server restart.

## Definition of Done (DoD)
- Room states are enumerated.
- Creation and destruction paths are specified.

## Negative cases
- Orphaned rooms after restart.
- Room with missing players.

## Edge cases
- Player disconnects during invite.

---

## Room States
- **Pending**: waiting for opponent (friend invite).
- **Active**: game in progress.
- **Completed**: game finished (results shown).
- **Abandoned**: auto-cleaned after timeout.

## Lifecycle Summary
- Create room when a match starts or invite is created.
- Transition to Active when both players join.
- Transition to Completed on game end.
- Cleanup removes room from memory.
