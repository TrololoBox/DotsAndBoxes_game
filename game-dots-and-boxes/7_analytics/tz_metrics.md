# TZ: Analytics Metrics

## Goal
Define analytics events and data captured.

## Inputs
- Analytics requirements.

## Outputs
- Metrics list and cadence.

## Internal logic
- Emit and aggregate metrics on state transitions.

## Definition of Done (DoD)
- Metrics cover all v1 reporting needs.

## Negative cases
- Missing metrics for game start/end.

## Edge cases
- Retry on failed analytics submission.

---

## Metrics (v1)
Collect **aggregate stats only** (no detailed event stream yet):

### Core Usage
- **Games played**: daily / weekly / monthly / all-time totals.
- **Unique users**: daily / weekly / monthly / all-time totals.

### Ads (v1.5 scope)
- **Ad views**: daily / weekly / monthly / all-time totals.
- **Ad clicks**: daily / weekly / monthly / all-time totals.

## Notes
- Keep schema extensible for future event-level analytics.
