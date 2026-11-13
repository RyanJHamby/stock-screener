# Position management

Position management is manual by design. The Robinhood integration is read-only.

## Setup

In `.env`:

```bash
ROBINHOOD_USERNAME=your_email@example.com
```

The password is never stored. You are prompted for it, and for an SMS code, each run.

## Run

```bash
python manage_positions.py                                  # basic analysis
python manage_positions.py --entry-dates entry_dates.json   # tax-aware
python manage_positions.py --export                         # write report to file
```

The tool fetches your positions, analyzes each one from cached market data (no extra
API calls), and recommends stop-loss adjustments.

## Example output (sample data)

> **This is illustrative sample output with made-up tickers, prices and dates. It is
> not a result from a real account or a real run.**

```
POSITION MANAGEMENT REPORT - STOP LOSS RECOMMENDATIONS
PORTFOLIO SUMMARY
Total Positions: 3
Need Stop Adjustment: 2
Average Gain: +8.47%

POSITION #2: NVDA
Entry: $495.00 | Current: $545.00 | Gain: +10.10%
Tax Treatment: SHORT_TERM | Days Held: 20
ACTION: TRAIL TO PROFIT
RECOMMENDED STOP LOSS: $519.75
  Locks in minimum +5.0% profit
  Technical: Phase 2 | 50 SMA: $512.30
```

## Stop-loss logic

| Gain | Recommendation | Stop level |
|---|---|---|
| 0-5% | Hold initial stop | Original stop |
| 5-10% | Trail to breakeven | Entry price |
| 10-20% | Trail to profit | Entry x (1 + locked_profit_pct/100) |
| 20-30% | Take 25-30% partial | Remaining at +10% profit |
| 30%+ | Take 50% partial | Remaining at tight trail |

```python
locked_profit_pct = min(gain_pct - 3, gain_pct * 0.5)
```

See `src/analysis/position_manager.py` for the implementation.

## Tax-aware filtering

Positions held 365 or more days are excluded from stop adjustments to preserve
long-term capital gains treatment. Provide entry dates in `entry_dates.json`:

```json
{
  "AAPL": "2024-10-18T00:00:00",
  "MSFT": "2023-05-10T00:00:00"
}
```
