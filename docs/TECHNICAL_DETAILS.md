# Technical details

Where this page and the code disagree, the code wins:
`src/screening/signal_engine.py` and `src/screening/phase_indicators.py`.

## Phase classification

Classifies a stock into one of four phases from the 50-day and 200-day SMAs, their
slopes, and price position, and returns a confidence score.

## Relative strength

63-day RS slope of the stock against SPY, scored on a linear scale:

```
rs_score = clip(5 + rs_slope * 16.67, 0, 10)
```

A slope of +0.3 scores 10, 0.0 scores 5, and -0.3 scores 0.

## Buy signal scoring (125 points max)

| Component | Max points |
|---|---|
| Trend structure / stage quality | 40 |
| Fundamentals (revenue growth 15, EPS growth 15, inventory 10, margins 10; neutral defaults when data is missing) | 40 |
| Risk/reward | 15 |
| Relative strength | 10 |
| Volume | 10 |
| Entry quality (pivot-point proximity) | 5 |
| VCP pattern bonus | +5 |

A signal is a buy when the score is at least **60**.

Risk/reward scoring: the target is 30% above the current price for Phase 2 stocks
(breakout level +25% for Phase 1). An R/R below 2:1 scores 0. At 2:1 the score is 3,
and it rises 6 points per 1.0 of R/R up to the 15-point cap (5:1 or better).
See the 2025-12-10 (Part 6) entry in the [CHANGELOG](../CHANGELOG.md).

## Sell signal scoring (100 points max)

| Component | Max points |
|---|---|
| Breakdown structure | 60 |
| Volume confirmation | 30 |
| RS weakness | 10 |
| Failed-breakout bonus | +10 (total capped at 100) |

A signal is a sell when the score is at least **60**. 80 or more is rated highest severity.

## Stop loss

`calculate_stop_loss` in `signal_engine.py`:

- Phase 2: the higher (tighter) of a stop just under the recent swing low and a stop
  just under the 50 SMA.
- Phase 1: below the base/consolidation low.
- Maximum risk is 10% from the current price; wider stops mean the trade is skipped.

Read the function for the exact constants.
