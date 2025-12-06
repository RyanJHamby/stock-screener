# Position Management Automation

## Overview

There are now two ways to use position management:

### 1. **Manual Mode** (On Your Local Machine)
```bash
python manage_positions.py
```

**When to use:**
- When you have 5-10 minutes in the morning
- Whenever you want to check stop losses manually
- For full control and review before taking action

**What happens:**
- Prompts for password (hidden input)
- Robinhood sends SMS to your phone
- You enter the SMS code
- Gets your positions from Robinhood
- Analyzes using cached market data (no extra API calls)
- Shows recommendations in terminal
- Optional: Export to file

**Security:**
- Password never stored
- Interactive only (can't be automated)
- SMS MFA required

### 2. **Automated Mode** (In GitHub Actions)
```bash
python automated_position_report.py
```

**When to use:**
- As part of your daily GitHub Actions workflow
- To automatically generate reports after each market scan
- For hands-off monitoring

**What happens:**
- Checks for ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD in environment
- If NOT set: Skips gracefully, doesn't block your scan
- If SET: Fetches positions and analyzes them
- Analyzes using cached market data (from daily scan - no extra API calls)
- Saves report to `./data/position_reports/position_management_*.txt`

**Security:**
- Username and password stored in GitHub Secrets (encrypted)
- Never committed to Git
- Only accessible to GitHub Actions

---

## Setup for Automation

### Step 1: Set GitHub Secrets

In your GitHub repository:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Create new secrets:
   - `ROBINHOOD_USERNAME` = your email
   - `ROBINHOOD_PASSWORD` = your password

### Step 2: Update Your Workflow

In `.github/workflows/daily_scan.yml` (or your workflow file):

```yaml
- name: Run stock screener
  run: python run_optimized_scan.py

# Optional: Generate position management report
- name: Generate position report
  if: always()  # Run even if scan fails
  run: python automated_position_report.py
  env:
    ROBINHOOD_USERNAME: ${{ secrets.ROBINHOOD_USERNAME }}
    ROBINHOOD_PASSWORD: ${{ secrets.ROBINHOOD_PASSWORD }}
```

### Step 3: Check Reports

After each run, the report will be saved to:
```
data/position_reports/position_management_YYYYMMDD_HHMMSS.txt
```

You can view it in your GitHub Actions logs or commit it to the repo for history.

---

## Key Design Decisions

### Why Two Scripts?

1. **Manual (`manage_positions.py`)** for you:
   - Interactive with human in the loop
   - SMS MFA for security
   - No password storage

2. **Automated (`automated_position_report.py`)** for CI/CD:
   - Fully automated, no prompts
   - Stored credentials (GitHub Secrets)
   - Graceful skip if credentials not provided

### Why Cache Data?

The position manager uses cached market data from your daily scan:
- ✓ No additional API calls to yfinance
- ✓ Lightning fast analysis
- ✓ Consistent with daily screening
- ✓ Zero impact on rate limits

### How It Works

```
Daily Scan (run_optimized_scan.py)
├─ Fetches 1 year price history for 3800+ stocks
├─ Caches all price data (1 year × 3800 = ~14MB)
└─ Caches fundamentals in Git

Position Analysis (automated_position_report.py)
├─ Reads Robinhood positions
├─ Looks up cached price data for each position
├─ Calculates Phase, SMA, swing lows
└─ Generates recommendations
```

No extra yfinance calls! Everything is cached from the daily scan.

---

## Example Workflow Integration

Complete `.github/workflows/daily_scan.yml`:

```yaml
name: Daily Stock Screening

on:
  schedule:
    - cron: '0 13 * * 1-5'  # 1 PM UTC, weekdays only
  workflow_dispatch:

jobs:
  screening:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install robin-stocks

      - name: Run stock screener
        run: python run_optimized_scan.py

      - name: Generate position report
        if: always()
        run: python automated_position_report.py
        env:
          ROBINHOOD_USERNAME: ${{ secrets.ROBINHOOD_USERNAME }}
          ROBINHOOD_PASSWORD: ${{ secrets.ROBINHOOD_PASSWORD }}

      - name: Commit results
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add -A
          git commit -m "Daily scan and position report" || true
          git push
```

---

## Troubleshooting

### "ROBINHOOD credentials not set - skipping position analysis"

This is **expected and normal**! It means:
- `ROBINHOOD_USERNAME` or `ROBINHOOD_PASSWORD` not in GitHub Secrets
- Position report will be skipped (gracefully)
- Your scan continues normally

To enable it: Set both secrets in GitHub repository settings.

### "Failed to login to Robinhood"

Check:
1. Username and password are correct
2. You can login to Robinhood web/app manually
3. If you have 2FA, make sure `by_sms=True` (it is by default)

### "Insufficient price data for analysis"

Position was added after the daily scan ran. It will be analyzed in tomorrow's run.

### "Invalid entry price (zero or negative)"

A position has a corrupted entry price in Robinhood. This is a Robinhood data issue, not your tool.

---

## Performance

- **Manual mode**: ~5 seconds per position (all cached)
- **Automated mode**: ~30 seconds for 5 positions
- **Total impact on daily scan**: Negligible (cached data only)

No rate limit concerns - no extra API calls!

---

## Privacy & Security

### What's Stored?

**GitHub Secrets (encrypted):**
- Your Robinhood username
- Your Robinhood password

**Local `.env` (NOT committed):**
- Your Robinhood username (for manual mode)

**Cached data (in Git):**
- Fundamentals (no credentials)
- Price history (no credentials)

### What's NOT Stored?

- ✗ Account balance
- ✗ Cash available
- ✗ Portfolio value
- ✗ Order history
- ✗ Personal info

The integration is **READ-ONLY** for positions only.

---

## Next Steps

1. **Try manual mode first:**
   ```bash
   python manage_positions.py
   ```

2. **If you like it, add to GitHub Actions:**
   - Set ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD in GitHub Secrets
   - Add `python automated_position_report.py` to your workflow

3. **Review reports:**
   - Check `data/position_reports/` for generated reports
   - Verify recommendations make sense
   - Manually adjust stops on Robinhood app

That's it! You now have fully automated position management.
