# Robinhood Position Fetcher - READ ONLY

This integration fetches your current stock positions from Robinhood.

## What It Does ✓

- Fetches tickers of stocks you currently own
- Shows entry prices (average buy price)
- Shows current prices and unrealized P/L %
- Shows number of shares

## What It Does NOT Do ✗

- Does NOT read account balance
- Does NOT read portfolio value
- Does NOT read buying power or cash
- Does NOT execute any trades
- Does NOT modify any positions
- Does NOT place any orders

**This is READ-ONLY for position tracking.**

---

## Setup

### 1. Install Library

```bash
pip install robin-stocks
```

This library provides API access to Robinhood (read-only mode).

### 2. Set Environment Variable

Add to your `.env` file (or export in terminal):

```bash
ROBINHOOD_USERNAME=your_email@example.com
```

**Password and SMS MFA are NEVER stored** - you'll be prompted interactively when running the scripts.

**Security note**: Never commit your `.env` file to Git. It's already in `.gitignore`.

---

## Usage

### Quick Check - See Your Positions

```bash
python check_positions.py
```

This will:
1. Prompt for your Robinhood password (never stored)
2. Log in to Robinhood and trigger SMS MFA to your phone
3. Prompt for the SMS code
4. Fetch your current positions
5. Display formatted report:
   - Ticker
   - Number of shares
   - Entry price
   - Current price
   - Unrealized P/L %
6. Option to export to text file
7. Auto-logout

### Example Output

```
============================================================
CURRENT ROBINHOOD POSITIONS (Read-Only)
Fetched: 2025-12-03 10:30:15
============================================================

1. AAPL
   Shares: 50
   Entry: $175.50
   Current: $182.30
   P/L: +3.87%

2. MSFT
   Shares: 25
   Entry: $380.00
   Current: $385.50
   P/L: +1.45%

3. NVDA
   Shares: 30
   Entry: $495.00
   Current: $489.20
   P/L: -1.17%

============================================================
Total positions: 3
============================================================

Tickers you currently own: AAPL, MSFT, NVDA
```

---

## Use Cases

### 1. Check Before Scanner Runs

See what you already own so you don't get duplicate buy signals:

```python
from src.data.robinhood_positions import RobinhoodPositionFetcher

fetcher = RobinhoodPositionFetcher()
fetcher.login()

owned_tickers = fetcher.get_position_tickers()
print(f"Currently own: {owned_tickers}")

fetcher.logout()
```

### 2. Compare Scanner Signals to Current Holdings

```python
# Get your positions
current_positions = fetcher.fetch_positions()

# Get scanner buy signals
buy_signals = [...]  # From scanner

# Filter out stocks you already own
new_opportunities = [
    signal for signal in buy_signals
    if signal['ticker'] not in [p['ticker'] for p in current_positions]
]
```

### 3. Auto-Update Trade Tracker

Fetch your positions and compare to your spreadsheet to find:
- Positions you forgot to log
- Exit prices when you've sold
- Current unrealized P/L

---

## Security

### Best Practices

1. **Use 2FA**: Enable two-factor authentication on Robinhood
2. **Environment variables**: Never hardcode credentials
3. **Don't commit .env**: Already in `.gitignore`
4. **Read-only**: This integration has NO trading capabilities
5. **Token storage**: robin-stocks stores auth token locally, logout when done

### What Permissions Does This Need?

The robin-stocks library uses your login credentials to access Robinhood's private API (the same API their mobile app uses).

**It can access**:
- Your positions (read-only)
- Historical orders (not implemented here)
- Account details (not accessed by our code)

**It cannot**:
- Place trades without explicit `rh.order_buy_*()` calls (we don't use these)
- Withdraw funds
- Change settings
- Access linked bank accounts

**Our implementation only calls**:
- `rh.login()` - Authenticate
- `rh.get_open_stock_positions()` - Fetch positions
- `rh.get_latest_price()` - Get current prices
- `rh.logout()` - Cleanup

No trading functions are used anywhere in the code.

---

## Troubleshooting

### "Login failed"

1. Check username/password are correct
2. If using 2FA, make sure MFA code is current (they expire quickly)
3. Try logging into Robinhood web/app to verify credentials work

### "Challenge required"

Robinhood sometimes requires extra verification:
- Log into the web app once
- Complete any security challenges
- Try the script again

### "Too many requests"

Robinhood rate limits API calls:
- Wait a few minutes
- Don't run the script repeatedly in quick succession

### "robin_stocks not found"

```bash
pip install robin-stocks
```

If that fails:
```bash
pip3 install robin-stocks
```

---

## Position Management - Stop Loss Recommendations

**NEW: Automated stop loss adjustment recommendations**

### Overview

The `manage_positions.py` tool fetches your Robinhood positions and analyzes each one to recommend:
- When to trail your stop losses up
- Exact new stop loss levels with detailed rationale
- When to take partial profits (25-50%)
- Warnings for Phase 3/4 transitions

**Important**: Only analyzes **SHORT-TERM** positions (held <1 year). Long-term positions are excluded to preserve favorable capital gains tax treatment.

### Usage

```bash
python manage_positions.py
```

With entry dates for tax treatment filtering:
```bash
python manage_positions.py --entry-dates entry_dates.json
```

Export report to file:
```bash
python manage_positions.py --export
```

### What It Recommends

**5-10% Gain**: Trail to Breakeven
- Moves stop to entry price (risk-free position)
- "If it pulls back, exit at breakeven with no loss"

**10-20% Gain**: Trail to +5% Profit or 50 SMA
- Locks in minimum 5% profit
- Trails to 50 SMA if it's higher
- "Let winner run while protecting gains"

**20-30% Gain**: Take Partial + Trail Remainder
- Recommends selling 25-30% at current price
- Trail remaining 70-75% with stop at +10% profit
- "Lock in some gains, let runners go"

**30%+ Gain**: Take 50% + Trail Tight
- Recommends selling 50% at current price
- Trail remaining 50% very tight (near 50 SMA)
- "Major winner - secure profits, give last piece tight room"

### Example Report

```
============================================================
POSITION MANAGEMENT REPORT - STOP LOSS RECOMMENDATIONS
============================================================

PORTFOLIO SUMMARY
------------------------------------------------------------
Total Positions: 3
Need Stop Adjustment: 2
Short-term (<1 year): 2
Long-term (1+ years): 1
Average Gain: +8.47%

⚠️  URGENT ACTIONS NEEDED
------------------------------------------------------------

NVDA (+10.10%)
  • Big winner - consider taking partial profits

================================================================================

POSITION #1: AAPL
################################################################################
Entry: $175.50 | Current: $182.30 | Gain: +3.87%
Tax Treatment: SHORT_TERM
Days Held: 45

ACTION: HOLD

RATIONALE:
Position up 3.9% - hold initial stop. Wait for 5-10% gain before adjusting.

Technical: Phase 2 | 50 SMA: $178.20

################################################################################

POSITION #2: MSFT
################################################################################
Entry: $380.00 | Current: $385.50 | Gain: +1.45%
Tax Treatment: LONG_TERM
Days Held: 400

ACTION: HOLD

RATIONALE:
LONG-TERM HOLD (400 days) - Preserve long-term capital gains tax rate.
No stop adjustment recommended.

################################################################################

POSITION #3: NVDA
################################################################################
Entry: $495.00 | Current: $545.00 | Gain: +10.10%
Tax Treatment: SHORT_TERM
Days Held: 20

ACTION: TRAIL TO PROFIT

✓ RECOMMENDED STOP LOSS: $519.75

RATIONALE:
Position up 10.1% - TRAIL STOP TO PROFIT.
  Move stop to $519.75 (locks in +5% gain minimum).
  Let position run while protecting profit floor.

Technical: Phase 2 | 50 SMA: $512.30

================================================================================
```

### Entry Dates JSON Format

Create a `entry_dates.json` file to track when you entered each position:

```json
{
  "AAPL": "2024-10-18T00:00:00",
  "MSFT": "2023-05-10T00:00:00",
  "NVDA": "2024-11-13T00:00:00"
}
```

**Why this matters**:
- Positions held 365+ days = Long-term capital gains (15-20% tax)
- Positions held <365 days = Short-term capital gains (ordinary income rate)
- The tool WON'T recommend adjusting stops for long-term positions to avoid triggering early sale

### Technical Analysis Used

Each position is analyzed for:
- Current Phase (1-4 stage analysis)
- 50-day SMA (key support level)
- 200-day SMA (major trend indicator)
- Recent swing lows (last 10 days)
- Distance from entry price

Stop recommendations use:
- Breakeven stops for small winners
- Profit-based stops for medium winners
- SMA-based trailing stops when above 50 SMA
- Tight trailing for big winners (30%+)

---

## Manual Trading Only

This tool is for **information only**. You still:
- Manually review buy signals
- Manually review stop loss recommendations
- Manually place orders on Robinhood app/web
- Manually adjust stop losses on the platform
- Manually exit positions

The integration provides **recommendations** - you make all trading decisions.
