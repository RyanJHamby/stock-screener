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

### 2. Set Environment Variables

Add to your `.env` file (or export in terminal):

```bash
ROBINHOOD_USERNAME=your_email@example.com
ROBINHOOD_PASSWORD=your_password
```

If you have 2FA enabled (recommended):

```bash
ROBINHOOD_MFA_CODE=123456  # Optional - can also enter interactively
```

**Security note**: Never commit your `.env` file to Git. It's already in `.gitignore`.

---

## Usage

### Quick Check - See Your Positions

```bash
python check_positions.py
```

This will:
1. Log in to Robinhood (will prompt for MFA if enabled)
2. Fetch your current positions
3. Display formatted report:
   - Ticker
   - Number of shares
   - Entry price
   - Current price
   - Unrealized P/L %
4. Option to export to text file
5. Auto-logout

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

## Integration with Scanner (Future)

Potential enhancements:

1. **Auto-filter buy signals**: Don't show stocks you already own
2. **Position monitoring**: Alert when your positions get sell signals from scanner
3. **Stop loss tracking**: Compare current prices to your stops
4. **Exit alerts**: Notify when positions drop below entry or trail stops

**None of these involve automated trading - all read-only.**

---

## Manual Trading Only

This tool is for **information only**. You still:
- Manually review buy signals
- Manually place orders on Robinhood app/web
- Manually set stop losses
- Manually exit positions

The integration just helps you track what you own so you can make informed decisions.
