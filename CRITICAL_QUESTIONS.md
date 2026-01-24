# Critical Questions

1) AFK choice behavior: should "continue with bot" actually swap in a bot opponent, or should it always abort? (Currently treated as abort to avoid inconsistent state.)

2) Blocked bot detection: Telegram API exceptions on delivery are treated as "delivery_failed" and abort the room. Is this acceptable, or should we attempt retries before aborting?

3) Active room idle TTL: should the 30-minute idle cleanup be configurable (env/config), or is a fixed value acceptable for now?
