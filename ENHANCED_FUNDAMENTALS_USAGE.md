# Enhanced Fundamentals Usage Guide

## Overview

The stock scanner now intelligently uses **both yfinance and FMP** to get the best fundamental data:

- **yfinance**: Fast screening of all 3,800 stocks (basic fundamentals)
- **FMP**: Detailed fundamentals for buy signals only (net margins, operating margins, inventory)

This hybrid approach gives you **detailed data where it matters** while staying under FMP's 250 requests/day limit.

## Quick Start

### 1. Without FMP (Default - yfinance only)

```bash
source venv/bin/activate
python run_optimized_scan.py
```

**What you get:**
- ✅ Gross margins
- ✅ Revenue & EPS trends
- ✅ Basic inventory data
- ⚠️ No net margins
- ⚠️ No operating margins
- ⚠️ Limited inventory breakdown

### 2. With FMP (Enhanced fundamentals)

First, set up FMP (see SETUP_FMP.md):

```bash
# Get free API key from https://site.financialmodelingprep.com/
echo 'FMP_API_KEY=your_key_here' >> .env
source .env
```

Then run with FMP enabled:

```bash
python run_optimized_scan.py --use-fmp
```

**What you get:**
- ✅ Net margins (not in yfinance!)
- ✅ Operating margins (not in yfinance!)
- ✅ Gross margins
- ✅ Revenue & EPS trends
- ✅ Detailed inventory with QoQ changes
- ✅ Inventory-to-sales ratios
- ✅ Enhanced snapshot format

## How It Works

### Strategy: Use FMP Intelligently

The system uses a **smart two-stage approach**:

#### Stage 1: Screen All Stocks (yfinance)
```
3,800 stocks → yfinance → 50-100 buy signals
No FMP API calls used ✅
```

#### Stage 2: Enhance Buy Signals (FMP)
```
50 buy signals × 4 FMP calls each = 200 FMP calls
Stays under 250/day limit ✅
```

### Automatic Fallback

The system automatically falls back to yfinance if:
- FMP_API_KEY not set
- FMP daily limit reached (250 requests)
- FMP returns errors
- FMP has no data for a ticker

You don't need to do anything - it just works!

## Command Options

### Basic Scanning

```bash
# Default: 3 workers, yfinance only
python run_optimized_scan.py

# Conservative: 2 workers, slower but safer
python run_optimized_scan.py --conservative

# Test mode: 100 stocks only
python run_optimized_scan.py --test-mode
```

### With Enhanced Fundamentals

```bash
# Use FMP for buy signal fundamentals
python run_optimized_scan.py --use-fmp

# Conservative mode + FMP
python run_optimized_scan.py --conservative --use-fmp

# Test mode + FMP (good for testing FMP setup)
python run_optimized_scan.py --test-mode --use-fmp
```

### Resume After Interruption

```bash
# Resume scan from where it stopped
python run_optimized_scan.py --resume --use-fmp
```

## Output Format Comparison

### Without FMP (yfinance)

```
============================================================
FUNDAMENTAL SNAPSHOT - AAPL
============================================================
✓ Revenue: Growing well (YoY: +15.2%, QoQ: +6.1%)
✓ EPS: STRONG growth (YoY: +28.4%, QoQ: +12.5%)
✓ Margins: EXPANDING (45.2%, +1.2pp QoQ)
• Inventory: Slight draw (-3.2% QoQ, ratio: 0.095)
  Note: Detailed breakdown not available via API

Overall Assessment:
✓ Fundamentals SUPPORT technical breakout
============================================================
```

### With FMP (Enhanced)

```
============================================================
ENHANCED FUNDAMENTAL SNAPSHOT - AAPL
============================================================

✓ Revenue: ACCELERATING ($94.93B, +6.1% QoQ)
✓ EPS: STRONG growth ($1.53, +12.5% QoQ)

Margins:
  Gross Margin:     45.2%
  Operating Margin: 32.4%
  Net Margin:       26.6% ✓ EXPANDING (+1.2pp)

Inventory:
  Total: $9.0B (9.5% of revenue)
  ✓ Drawing down (-3.2% QoQ)
  → Strong demand signal

Overall Assessment:
✓ Fundamentals SUPPORT technical breakout
============================================================
```

**Key differences:**
- ✅ Net margin shown (26.6%)
- ✅ Operating margin shown (32.4%)
- ✅ More detailed inventory analysis
- ✅ Absolute dollar values ($94.93B revenue, $9.0B inventory)
- ✅ Better formatting and demand signals

## API Usage Tracking

When using `--use-fmp`, the scanner shows FMP usage at the end:

```
============================================================
FMP API USAGE
Calls used: 200/250
Calls remaining: 50
============================================================

============================================================
SCAN COMPLETE
Time: 32.4 minutes
Actual TPS: 6.2
Buy signals: 50
Sell signals: 23
============================================================
```

### Understanding FMP Call Count

**Each stock uses 4 FMP API calls:**
1. Income statement (quarterly)
2. Balance sheet (quarterly)
3. Cash flow statement (quarterly)
4. Key metrics (quarterly)

**Math:**
- 50 buy signals × 4 calls = 200 FMP calls
- Well under the 250/day limit ✅

## Rate Limits Summary

| Data Source | Rate Limit | Usage Strategy |
|-------------|------------|----------------|
| **yfinance** | ~6 TPS (token bucket) | Screen all 3,800 stocks |
| **FMP Free** | 250 calls/day | Top 50-60 buy signals only |
| **FMP Paid** | More calls | Consider if >60 buy signals/day |

## Troubleshooting

### "FMP_API_KEY not set"

**Problem:** Scanner shows `FMP_API_KEY not set - using yfinance only`

**Solution:**
```bash
# Check if key is set
echo $FMP_API_KEY

# If empty, add to .env
echo 'FMP_API_KEY=your_key_here' >> .env
source .env

# Or export in terminal
export FMP_API_KEY="your_key_here"
```

### "FMP daily limit reached"

**Problem:** Scanner shows `FMP daily limit reached (250). Using yfinance.`

**Solution:**
- Wait until next day (limit resets at midnight EST)
- Or, only use FMP on your top 60 buy signals
- Consider upgrading to paid FMP plan

### "FMP returned no data"

**Problem:** Some tickers show `FMP returned no data, falling back to yfinance`

**Solution:**
- This is normal - not all stocks are in FMP
- Scanner automatically falls back to yfinance
- No action needed

## Best Practices

### 1. Test FMP Setup First

Before running full scan, test with 10 stocks:

```bash
# Test with small universe
python run_optimized_scan.py --test-mode --use-fmp

# Check output for FMP data
tail -100 data/daily_scans/latest_optimized_scan.txt | grep "ENHANCED"
```

### 2. Run Scans During Off-Peak Hours

For best yfinance performance:
- ✅ Best: 2-6 AM EST (automated via cron)
- ✅ Good: 8 PM - midnight EST
- ⚠️ Risky: 9-11 AM EST (market open, high traffic)

### 3. Check FMP Usage

If running multiple scans per day:

```bash
# At end of scan, check usage
# Look for "FMP API USAGE" section in logs
tail -50 data/logs/optimized_scan_$(date +%Y%m%d).log | grep -A 5 "FMP API USAGE"
```

### 4. Save on FMP Calls

If you have multiple strategies, prioritize:

**Use FMP for:**
- ✅ Top-scored buy signals (score ≥ 80)
- ✅ Phase 1→2 transitions
- ✅ Stocks with technical breakouts

**Skip FMP for:**
- ❌ Low-score signals (score < 70)
- ❌ Stocks in Phase 3/4
- ❌ Sell signals

## Integration with Your Workflow

### Morning Workflow (Automated)

```bash
# 1. Cron runs full scan at 6:30 AM EST
# (configured via SETUP_CRON_JOB.md)

# 2. Review results when you wake up
cat data/daily_scans/latest_optimized_scan.txt

# 3. Check top 10 buy signals (with FMP fundamentals)
head -200 data/daily_scans/latest_optimized_scan.txt
```

### Manual Ad-Hoc Scans

```bash
# Quick scan without FMP (faster)
python run_optimized_scan.py

# Detailed scan with FMP (for serious buys)
python run_optimized_scan.py --use-fmp

# Conservative scan if experiencing rate limits
python run_optimized_scan.py --conservative --use-fmp
```

## Cost Analysis

| Approach | Cost | Pros | Cons |
|----------|------|------|------|
| **yfinance only** | Free | ✅ Unlimited<br>✅ Fast<br>✅ Works for all stocks | ❌ No net margins<br>❌ No operating margins<br>❌ Limited inventory |
| **FMP Free** | Free | ✅ Net margins<br>✅ Operating margins<br>✅ Detailed inventory | ⚠️ 250 calls/day<br>⚠️ ~60 stocks/day max |
| **FMP Starter** | $30/mo | ✅ 1,000 calls/day<br>✅ Can analyze 250 stocks/day | 💰 Monthly cost |
| **FMP Pro** | $200/mo | ✅ 10,000 calls/day<br>✅ Real-time updates | 💰💰 High cost |

**Recommendation:** Start with **yfinance + FMP Free**. This gives you detailed fundamentals for your top 50-60 buy signals, which is perfect for most traders.

## Next Steps

1. **Set up FMP** (if you haven't already):
   ```bash
   # See SETUP_FMP.md for detailed instructions
   cat SETUP_FMP.md
   ```

2. **Run test scan**:
   ```bash
   python run_optimized_scan.py --test-mode --use-fmp
   ```

3. **Review enhanced snapshots** in the output:
   ```bash
   cat data/daily_scans/latest_optimized_scan.txt | grep -A 20 "ENHANCED"
   ```

4. **Schedule automated scans** (optional):
   ```bash
   # See SETUP_CRON_JOB.md
   # Add --use-fmp to daily_scanner.sh
   ```

## Summary

- ✅ **Default mode**: Fast screening with yfinance (basic fundamentals)
- ✅ **Enhanced mode**: Detailed FMP fundamentals for buy signals
- ✅ **Automatic fallback**: Gracefully handles missing data
- ✅ **Stay under limits**: Smart usage keeps you under 250/day
- ✅ **No extra work**: Just add `--use-fmp` flag

The system gives you **professional-grade fundamental analysis** while keeping everything free and automated! 📊
