# Methodology and design notes

Moved out of the README. For scoring details, `src/screening/signal_engine.py` is
the source of truth; see [TECHNICAL_DETAILS.md](TECHNICAL_DETAILS.md).

## Attribution

The buy-signal criteria are based on Mark Minervini's Trend Template (SEPA),
from his books *Trade Like a Stock Market Wizard* (2013) and *Think & Trade Like a
Champion* (2017). The four-phase classification follows Stan Weinstein's stage
analysis (*Secrets for Profiting in Bull and Bear Markets*). The fundamentals
screen draws on William O'Neil's CANSLIM, and relative strength and market regime
awareness draw on IBD methodology.

## The Trend Template (8 criteria)

Buy signals trigger only for Phase 2 stocks that pass 7 of 8:

1. Price > 150 SMA and 200 SMA
2. 150 SMA > 200 SMA
3. 200 SMA trending up for at least 1 month
4. 50 SMA > 150 SMA > 200 SMA
5. Price > 50 SMA
6. Price at least 30% above the 52-week low
7. Price within 25% of the 52-week high
8. Relative strength: Minervini uses an RS rank of 70 or more; this project uses an RS slope of +0.15 or more

## Phases

- **Phase 1 (base building):** consolidation after a decline; SMAs flattening. Not a buy.
- **Phase 2 (uptrend):** 50 > 150 > 200 SMA, all rising, price above all of them. The buy zone.
- **Phase 3 (distribution):** SMAs flattening or crossing, momentum weakening. Sell zone.
- **Phase 4 (downtrend):** 50 SMA below 200 SMA, both falling, price below both. Avoid.

## Design choices

1. **Cache-first.** yfinance is rate limited, so the scan runs at about 1 request per
   second. Fundamentals change quarterly, so they are stored in Git as JSON with a
   `fetched_at` timestamp and refreshed only when stale (more than 7 days old during
   earnings windows, more than 90 days otherwise). Price data is always fetched fresh.
2. **Confirmed uptrends only.** Buy signals come from Phase 2 stocks only.
3. **Relative strength as a filter.** 63-day RS slope against SPY, scored on a linear scale.
4. **Linear formulas over buckets.** Scores interpolate smoothly instead of jumping at
   thresholds. Trailing stops scale with gain the same way.
5. **Market regime awareness.** Buy signals are generated only when SPY is in Phase 1 or 2
   and at least 15% of stocks are in Phase 2. Sell signals are always generated.
6. **Read-only position management.** The Robinhood integration only reads positions and
   never calls order functions. A human places any trade.

## Caveat on the caching claim

An earlier README said the Git-based cache gives a "74% reduction in API calls".
That figure appears only as a checked box in `DEPLOYMENT_CHECKLIST.md` (15,200 to
3,926 calls) and has no captured run behind it, so it was removed from the README.
