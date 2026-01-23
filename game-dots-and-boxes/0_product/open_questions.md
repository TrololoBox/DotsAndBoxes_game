# Open Questions

> This file collects unresolved product decisions. No assumptions should be made until these are answered.

## Answered Decisions
1. **Supported board sizes**: 3x3, 4x4, and 5x5 squares (three selectable options).
2. **Default board size for first-time users**: none; users must choose a board size before searching/joining a match.
3. **Fallback emoji when both pick the same**: 👤 (neutral silhouette).
4. **Edge color themes (default presets)**:
   - **Classic**: Player A `#2F80ED` (blue), Player B `#EB5757` (red), Neutral `#BDBDBD`, Background `#F2F2F2`.
   - **Forest**: Player A `#219653` (green), Player B `#F2994A` (orange), Neutral `#BDBDBD`, Background `#F2F2F2`.
   - **Night**: Player A `#56CCF2` (cyan), Player B `#BB6BD9` (purple), Neutral `#4F4F4F`, Background `#1B1B1B`.
5. **Custom colors**: presets only for v1; keep configuration extensible to add custom colors later.
6. **Turn timers (simplified)**: PvE 60s per turn; PvP 45s per turn.
7. **AFK timeout threshold**: after 2 consecutive turn timeouts, show the AFK choice flow.
8. **Max concurrent games per user**: 1 active game.
9. **Soft-ad offer wording/timing**: after match results, show a message with a button “Посмотреть рекламу”. On click, trigger ad playback (stub for now).
10. **Telegram payment/donation providers**: not selected yet; include a menu button for donations (provider integration TBD).
11. **Chat support**: private chats only (no group chats).
12. **Analytics (v1)**: aggregate stats only — total games played and unique users (daily/weekly/monthly/all-time), plus ad views/clicks (v1.5 scope).
13. **Localization**: Russian only for v1; add English after core game stability.
14. **Player name formatting**: display Telegram username only; no emojis/custom names.
15. **Rematch behavior**: restart the same match with same starting player, same board size, same colors, same emojis.
