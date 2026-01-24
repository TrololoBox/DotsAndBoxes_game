# Dots & Boxes Bot Hardening Report

## 0) Authoritative State Ownership (P0)

### Problem
State mutations were spread across handlers, allowing concurrent callbacks and bot moves to modify room state directly. This risks desyncs, race conditions, and invalid updates.

### Fix
Introduced a single authoritative Game Engine (`state/engine.py`). All state mutations now flow through engine entry points:
- `start_game`
- `apply_edge_move`
- `apply_numbered_move`
- `apply_bot_edge`
- `update_page`
- `end_game` / `abandon_room`

Rendering and keyboard generation are read-only consumers of state.

### Why it works
The engine enforces validation and state transitions consistently. This prevents handlers from mutating state without validation and ensures monotonic state updates with versioning.

### Authoritative flow (diagram)
```
Telegram Callback
   ↓
Bot Handler (read-only routing)
   ↓
Engine Validation (room exists, active, version match, turn, edge free)
   ↓
Engine Mutation (move applied, version++, move_number++, turn advanced)
   ↓
Renderer + Keyboard (read-only, uses room.state_version)
```

### Forbidden
- Handlers must not directly mutate `Room` fields (except storing message IDs).
- No direct `Room.state` changes outside the engine.

### Negative cases
- Callback for non-existing room → rejected.
- Player not in room → rejected.
- Stale callback version → rejected.

### Edge cases
- Both players click at nearly the same time → only one move accepted due to version check.
- Late callback after bot move → rejected due to version mismatch.

---

## 1) Callback Race & Double Tap Protection (P0)

### Problem
Callbacks did not carry a version; stale keyboards could mutate state.

### Fix
Added `state_version` to all in-game callbacks:
- `e:h:r:c:version`
- `num:number:version`
- `pg:page:version`
- `afk:choice:version`

Validation checks:
- Room exists
- Room active
- Version matches
- Edge still free
- User's turn

### Why it works
State version increments on every mutation. Old callbacks can never match the latest version; they are rejected deterministically.

### Callback validation flow
```
Parse callback → find room → verify room active → verify version → verify player → verify turn → verify edge → apply move
```

### Negative cases
- Old keyboard pressed → stale version, rejected with toast.
- Double tap on same edge → second callback rejected (version mismatch or edge occupied).

### Edge cases
- Telegram retries callback delivery → version mismatch, rejected.
- Pagination button from previous page → version mismatch, rejected.

---

## 2) Room Lifecycle & Cleanup (P0)

### Problem
Room states were incomplete and some rooms could become dead (abandoned but never cleaned).

### Fix
Room lifecycle states:
- `created`
- `waiting`
- `active`
- `finished`
- `aborted`

All termination paths use a single `end_game(reason)` via engine.
Cleanup handles:
- Pre-game rooms (created/waiting) timeout.
- Active rooms idle timeout.
- Finished/aborted rooms TTL cleanup.

### Room lifecycle diagram
```
created → active → finished
created → waiting → active → finished
active → aborted
waiting → aborted (timeout)
```

### Cleanup rules & TTL strategy
- created/waiting: 10 min
- active idle: 30 min
- finished: 5 min
- aborted: 5 min

### Negative cases
- Invite never accepted → room cleaned after TTL.
- Player leaves → room aborted and cleaned.

### Edge cases
- Bot restart → cleanup clears in-memory rooms and queues.
- User blocks bot → delivery failure aborts room to avoid dead lock.

---

## 3) AFK & Turn Timer Hardening (P0)

### Problem
Timer expiry could race with a valid move. There was no state version check.

### Fix
Turn timer API now accepts `expected_version`. Timeout handling ignores stale timers if the room version has advanced.

### Why it works
Timer expiration only applies to the version it was scheduled for. Any move increments the version, invalidating old timers.

### Negative cases
- Timeout fires after a move → ignored.
- Multiple timers for same turn → only first matching version applies.

### Edge cases
- Rapid move sequence → timer check fails safe (ignored).

---

## 4) UX Feedback Consistency (P0)

### Problem
Invalid interactions sometimes returned silently or used ad-hoc strings.

### Fix
Centralized UX toasts in `telegram_pkg/toasts.py` and `telegram_pkg/ux.py`.
All invalid paths call `answerCallbackQuery` with deterministic messages.

### UX feedback mapping (examples)
- `stale_callback` → "Клавиатура устарела..."
- `edge_occupied` → "Сюда уже ходили..."
- `room_not_found` → "Игра не найдена..."

### Negative cases
- Outdated keyboard click → toast + no mutation.
- Invalid numbered input → toast + no mutation.

### Edge cases
- Unknown callback → toast unknown error (no silent failure).

---

## 5) Pagination + Numbered Mode Safety (P0)

### Problem
Old paginated keyboards could still change page, and numbered inputs lacked version validation.

### Fix
Pagination callbacks carry version. Server validates page bounds using `game/lines_pagination.py`.
Numbered mode validation ensures:
- Number is valid
- Edge exists
- Edge is still free

### Why it works
Old keyboards and invalid numbers are rejected by server-side validation.

### Negative cases
- Old page button pressed → stale version.
- Number out of range → rejected.

### Edge cases
- Board size changes → mapping is deterministic, callbacks must match version.

---

## 6) Logging & Observability (P0)

### Problem
Logs were inconsistent and not structured for replay.

### Fix
Introduced structured JSON logs (`state/logging_utils.py`) with required fields:
- game_id
- room_id
- user_id
- move_number
- state_version
- reason (for rejection)

### Example log entries
```json
{"event": "move_applied", "game_id": "abc123", "room_id": "abc123", "user_id": 42, "move_number": 5, "state_version": 12, "edge_id": "h_2_1", "captures": 1, "extra_turn": true}
{"event": "action_rejected", "game_id": "abc123", "room_id": "abc123", "user_id": 99, "reason": "stale_callback", "expected_version": 11, "state_version": 12, "move_number": 5}
```

---

# WORK BREAKDOWN STRUCTURE (WBS)

Task ID: T01  
Title: Centralize authoritative game engine  
Priority: P0  
Type: Refactor  
Depends on: []  
Parallelizable with: [T02, T03, T05]  
Owner role: Game-engine  
Deliverables:
- `state/engine.py` with validated mutation paths  
DoD:
- All handlers mutate state only through engine  
Tests / Scenarios:
- Fast double-tap edge → 1 move accepted, 1 rejected

Task ID: T02  
Title: Add state version to callbacks and validation  
Priority: P0  
Type: Safety  
Depends on: [T01]  
Parallelizable with: [T03, T04]  
Owner role: Telegram handlers  
Deliverables:
- Versioned callbacks in keyboards + parser  
DoD:
- Stale callbacks rejected with toast  
Tests / Scenarios:
- Use old keyboard after move → rejected

Task ID: T03  
Title: Room lifecycle states + cleanup hardening  
Priority: P0  
Type: Safety  
Depends on: [T01]  
Parallelizable with: [T02, T05]  
Owner role: Backend  
Deliverables:
- Room states created/waiting/active/finished/aborted  
DoD:
- Aborted rooms cleaned, players released  
Tests / Scenarios:
- Leave game → room aborted and cleaned

Task ID: T04  
Title: Pagination + numbered validation  
Priority: P0  
Type: Bugfix  
Depends on: [T02]  
Parallelizable with: [T05]  
Owner role: Telegram handlers  
Deliverables:
- Page bounds validation, numbered input validation  
DoD:
- Invalid page/number rejected  
Tests / Scenarios:
- Page > max → toast + no change

Task ID: T05  
Title: Structured logging + UX mapping  
Priority: P0  
Type: Safety  
Depends on: []  
Parallelizable with: [T01, T02, T03, T04]  
Owner role: Backend  
Deliverables:
- JSON logs + toast mapping  
DoD:
- Every rejection logs reason and version  
Tests / Scenarios:
- Trigger stale callback → log entry with reason

Task ID: T06  
Title: AFK timer version checks  
Priority: P1  
Type: Safety  
Depends on: [T01, T02]  
Parallelizable with: []  
Owner role: Backend  
Deliverables:
- Timer ignores stale versions  
DoD:
- Timer applies only to current version  
Tests / Scenarios:
- Timeout after move → ignored

Task ID: T07  
Title: Documentation + diagrams  
Priority: P2  
Type: Docs  
Depends on: [T01, T02, T03, T05]  
Parallelizable with: []  
Owner role: QA  
Deliverables:
- Hardening report with diagrams  
DoD:
- All required sections present  
Tests / Scenarios:
- N/A

# DEPENDENCY GRAPH (TEXT)
T01 -> T02, T03, T06  
T02 -> T04, T06  
T03 -> T07  
T05 -> T07

# PARALLEL WORKSTREAMS
Workstream A: State & Engine (T01)  
Workstream B: Telegram Callbacks & UX feedback (T02, T05)  
Workstream C: Timers & AFK (T06)  
Workstream D: Pagination & Numbered Safety (T04)  
Workstream E: Docs & Reporting (T07)

# EXECUTION SPRINT PLAN
Sprint 0 (P0): T01, T02, T03, T04, T05  
Sprint 1 (P1): T06  
Sprint 2 (P2): T07
