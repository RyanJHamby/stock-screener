```markdown
# Full Market Scanner - All US-Listed Stocks

## Overview

This is an **enterprise-grade full market scanner** that processes **ALL publicly traded US stocks** (5,000-8,000 stocks) daily with intelligent rate limiting, progress tracking, and comprehensive reporting.

## Key Features

### 🌎 Complete Market Coverage
- Fetches latest list of ALL US-listed stocks daily
- NASDAQ, NYSE, AMEX exchanges
- Auto-updates universe each day
- 5,000-8,000 stocks scanned

### ⚡ Intelligent Processing
- **Rate Limiting**: 1 request/second (1 TPS) to respect API limits
- **Progress Tracking**: Resume from interruptions
- **Incremental Saving**: Progress saved every 100 stocks
- **Smart Filtering**: Removes penny stocks, low-volume stocks, ETFs
- **Estimated Runtime**: 2-3 hours for full market scan

### 📊 Comprehensive Filtering

**Automatic Filters**:
- Minimum price: $5.00 (configurable)
- Maximum price: $10,000 (configurable)
- Minimum volume: 100,000 shares/day (configurable)
- Removes: ETFs, funds, warrants, preferred shares, test symbols

### 🎯 Daily Execution
- Scheduled for 6:30 AM EST (after Yahoo Finance updates)
- Automatic via cron job
- Logs all activity
- Saves comprehensive reports

### 💾 Results Management
- **Top 50 buy signals**: Detailed analysis with fundamentals
- **All buy signals**: Complete ticker list
- **Top 30 sell signals**: Detailed breakdown analysis
- **All sell signals**: Complete ticker list
- **Market metrics**: SPY trend, breadth, risk regime
- **Saved to**: `./data/daily_scans/`

---

## Quick Start

### 1. Test Mode (First Time)

Test with only 100 stocks to verify everything works:

```bash
source venv/bin/activate
python run_full_market_scan.py --test-mode
```

This takes ~2 minutes and helps you understand the output.

### 2. Full Market Scan

Scan all US stocks:

```bash
source venv/bin/activate
python run_full_market_scan.py
```

**Expected Duration**: 2-3 hours for ~6,000 stocks at 1 TPS

### 3. Resume After Interruption

If the scan is interrupted (Ctrl+C, connection loss, etc.):

```bash
python run_full_market_scan.py --resume
```

It will pick up exactly where it left off!

### 4. Clear Progress & Start Fresh

```bash
python run_full_market_scan.py --clear-progress
```

---

## Daily Automated Execution

### Setup Cron Job (6:30 AM EST Daily)

1. **Edit crontab**:
   ```bash
   crontab -e
   ```

2. **Add this line** (replace path with your actual path):
   ```cron
   # Daily market scan at 6:30 AM EST
   30 6 * * 1-5 /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh
   ```

   This runs Monday-Friday at 6:30 AM EST.

3. **Verify cron job**:
   ```bash
   crontab -l
   ```

### Check Cron Logs

Logs are saved to `./data/logs/daily_scan_YYYYMMDD.log`

```bash
# View today's log
tail -f ./data/logs/daily_scan_$(date +%Y%m%d).log

# View all recent logs
ls -lh ./data/logs/
```

---

## Command Line Options

### Basic Usage

```bash
python run_full_market_scan.py [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--resume` | Resume from previous progress | False |
| `--clear-progress` | Clear progress and start fresh | False |
| `--min-price PRICE` | Minimum stock price | $5.00 |
| `--max-price PRICE` | Maximum stock price | $10,000 |
| `--min-volume VOL` | Minimum avg daily volume | 100,000 |
| `--rate-limit SEC` | Seconds between API calls | 1.0 (1 TPS) |
| `--test-mode` | Process only first 100 stocks | False |

### Examples

```bash
# Higher quality stocks only
python run_full_market_scan.py --min-price 10 --min-volume 500000

# Faster scan (but may hit rate limits)
python run_full_market_scan.py --rate-limit 0.5

# Resume interrupted scan
python run_full_market_scan.py --resume

# Test mode
python run_full_market_scan.py --test-mode
```

---

## How It Works

### 1. Universe Fetching

Every run:
1. Fetches latest NASDAQ stocks from NASDAQ FTP
2. Fetches latest NYSE/AMEX stocks from NASDAQ FTP
3. Combines and deduplicates (~8,000 symbols)
4. Filters out ETFs, funds, warrants, preferred shares
5. Results in ~6,000 tradable stocks
6. **Cached for 24 hours** to avoid refetching

### 2. Stock Filtering

Each stock is checked:
- Price range: $5 - $10,000 (default)
- Volume: >100,000 shares/day (default)
- Data quality: Must have 200+ days of history
- Removes untradable stocks before analysis

### 3. Batch Processing

```
For each stock:
  1. Rate limit (wait 1 second)
  2. Fetch price history (2 years)
  3. Check filters (price, volume)
  4. Classify phase (1-4)
  5. Calculate RS vs SPY
  6. Fetch fundamentals (if Phase 1/2)
  7. Save progress every 100 stocks

Total time: ~6,000 stocks × 1 sec = ~1.7 hours
(Plus network overhead = 2-3 hours total)
```

### 4. Signal Generation

After all stocks analyzed:
1. Analyze SPY and calculate market breadth
2. Determine if market conditions support buy signals
3. Score all Phase 1/2 stocks for buy signals (≥70)
4. Score all Phase 3/4 stocks for sell signals (≥60)
5. Sort by score (highest first)

### 5. Report Generation

Creates comprehensive report:
- **Top 50 buys**: Full details + fundamental snapshots
- **Remaining buys**: Ticker list only
- **Top 30 sells**: Full details
- **Remaining sells**: Ticker list only
- **Market context**: SPY, breadth, risk regime

---

## Output Files

### Daily Reports

Location: `./data/daily_scans/`

Files:
- `market_scan_YYYYMMDD_HHMMSS.txt` - Full timestamped report
- `latest_scan.txt` - Symlink to most recent scan

### Progress Files

Location: `./data/batch_results/`

Files:
- `batch_progress.pkl` - Resume data (deleted after completion)

### Logs

Location: `./data/logs/`

Files:
- `daily_scan_YYYYMMDD.log` - Daily scan logs
- Automatically cleaned up after 30 days

### Cache

Location: `./data/cache/`

Files:
- `us_stock_universe.pkl` - Stock universe (24hr cache)
- `SPY_prices_2y_1d.pkl` - SPY data (24hr cache)
- `{TICKER}_prices_2y_1d.pkl` - Individual stock data (24hr cache)

---

## Sample Output

```
================================================================================
FULL MARKET SCAN - ALL US-LISTED STOCKS
Scan Date: 2025-11-26
Generated: 2025-11-26 09:30:15 EST
================================================================================

SCANNING STATISTICS
--------------------------------------------------------------------------------
Total Universe: 6,247 stocks
Analyzed: 4,832 stocks
Filtered Out: 1,415 stocks
Processing Time: 2.3 hours
Buy Signals: 127
Sell Signals: 89

================================================================================
BENCHMARK SUMMARY
================================================================================
SPY Trend Classification:
  Phase: 2 - Uptrend/Breakout
  Trend: Bullish
  Confidence: 85%

Market Breadth: 42.3% in Phase 2
Market Regime: RISK-ON (Moderate)

Interpretation:
  → Favorable environment for breakout trades
  → Focus on Phase 2 breakouts with strong RS

================================================================================
TOP BUY SIGNALS (Score >= 70) - 127 Total
================================================================================

################################################################################
BUY #1: TICKER | Score: 92/100
################################################################################
Phase: 2
Breakout Price: $45.25
RS Slope: 3.42
Volume: 2.1x average

Key Reasons:
  • In Phase 2 (Uptrend)
  • Fresh breakout above $45.25
  • Excellent RS momentum: 3.42
  • Strong volume expansion: 2.1x
  • Volatility squeeze resolving higher

FUNDAMENTAL SNAPSHOT
✓ Revenue: ACCELERATING (YoY: +28.3%, QoQ: +9.2%)
✓ EPS: STRONG growth (YoY: +35.1%)
✓ Margins: EXPANDING (38.2%, +1.8pp QoQ)
✓ Fundamentals SUPPORT technical breakout

[... top 50 with full details ...]

================================================================================
ADDITIONAL BUY SIGNALS (77 more)
================================================================================
TICKER1, TICKER2, TICKER3, ...

================================================================================
TOP SELL SIGNALS (Score >= 60) - 89 Total
================================================================================

[... top 30 with full details ...]

================================================================================
END OF DAILY MARKET SCAN
================================================================================
```

---

## Performance & Scalability

### Current Performance

- **Stock Universe**: ~6,000 stocks
- **Rate Limit**: 1 request/second (1 TPS)
- **Processing Time**: ~2-3 hours
- **CPU Usage**: Minimal (I/O bound)
- **Memory Usage**: ~500MB
- **Storage**: ~50MB per day (reports + cache)

### Optimization Options

If you need faster processing:

1. **Parallel Processing** (Advanced):
   - Use multiple API keys
   - Run 2-3 parallel processes
   - Reduces time to ~1 hour

2. **Higher Rate Limit** (Risky):
   ```bash
   python run_full_market_scan.py --rate-limit 0.5  # 2 TPS
   ```
   Warning: May trigger rate limiting from Yahoo Finance

3. **Pre-filtering** (Recommended):
   ```bash
   # Only scan higher quality stocks
   python run_full_market_scan.py --min-price 10 --min-volume 500000
   ```
   Reduces universe to ~3,000 stocks, ~1 hour runtime

### Handling Interruptions

The scanner is designed to handle interruptions gracefully:

- **Network issues**: Retries with exponential backoff
- **API failures**: Continues with next stock
- **Keyboard interrupt** (Ctrl+C): Saves progress cleanly
- **Power loss**: Resume from last checkpoint

Always run with `--resume` after any interruption.

---

## Monitoring

### Real-Time Progress

```bash
# Watch progress in real-time
tail -f ./data/logs/daily_scan_$(date +%Y%m%d).log
```

Progress updates every 10 stocks:
```
Progress: 1000/6247 (16.0%) | Rate: 0.98/sec | ETA: 1:29:15
Progress: 1010/6247 (16.2%) | Rate: 0.99/sec | ETA: 1:28:42
```

### Check Results

```bash
# View latest scan
cat ./data/daily_scans/latest_scan.txt | less

# Count buy/sell signals
grep "BUY #" ./data/daily_scans/latest_scan.txt | wc -l
grep "SELL #" ./data/daily_scans/latest_scan.txt | wc -l
```

---

## Troubleshooting

### Issue: "Failed to fetch stock universe"

**Cause**: Network issue or NASDAQ FTP down

**Solution**:
1. Check internet connection
2. Try again in 5 minutes
3. Check NASDAQ FTP status

### Issue: "Rate limit exceeded"

**Cause**: Making requests too fast

**Solution**:
```bash
# Increase delay
python run_full_market_scan.py --rate-limit 1.5
```

### Issue: Scan taking too long

**Current Time**: 2-3 hours is normal for ~6,000 stocks

**To Speed Up**:
```bash
# Filter for higher quality stocks only
python run_full_market_scan.py --min-price 10 --min-volume 500000
```

### Issue: Out of disk space

**Solution**:
```bash
# Clear old scans (keeps last 30 days)
find ./data/daily_scans -mtime +30 -delete

# Clear cache
rm -rf ./data/cache/*.pkl

# Clear old logs
find ./data/logs -mtime +30 -delete
```

---

## Comparison: Quick vs Full Scan

| Feature | Quick Scan (original) | Full Market Scan |
|---------|----------------------|------------------|
| **Stocks** | 30-100 (manual list) | 6,000+ (all US stocks) |
| **Runtime** | 30 seconds - 2 minutes | 2-3 hours |
| **Universe** | Static config file | Auto-updated daily |
| **Filtering** | Manual | Automatic |
| **Resume** | No | Yes |
| **Progress** | No tracking | Full tracking |
| **Rate Limiting** | Best effort | Enforced 1 TPS |
| **Use Case** | Quick checks, testing | Daily market analysis |

---

## Best Practices

### Daily Workflow

1. **Let cron run automatically** at 6:30 AM EST
2. **Check results** around 9:00 AM:
   ```bash
   cat ./data/daily_scans/latest_scan.txt | less
   ```
3. **Review top signals** (first 20-30)
4. **Research candidates** further
5. **Execute trades** per your strategy

### Data Management

- **Scans**: Keep last 30 days
- **Logs**: Keep last 30 days
- **Cache**: Auto-refreshes daily
- **Progress**: Auto-cleans after completion

### Reliability

- **Cron monitoring**: Check logs weekly
- **Error handling**: Scanner continues on errors
- **Resume capability**: Always use `--resume` flag
- **Logging**: All activity logged for debugging

---

## Advanced Configuration

### Custom Universe

To scan a custom list instead of all US stocks:

1. Create `custom_tickers.txt`:
   ```
   AAPL
   MSFT
   GOOGL
   ...
   ```

2. Modify script to load from file (see code)

### Email Notifications

Add to `daily_scanner.sh`:
```bash
# Email results
cat ./data/daily_scans/latest_scan.txt | mail -s "Daily Market Scan" your@email.com
```

### Slack Integration

See existing notification modules for Slack webhooks.

---

## System Requirements

- **Python**: 3.8+
- **RAM**: 1GB minimum
- **Storage**: 10GB recommended
- **Network**: Stable internet connection
- **Runtime**: 3-4 hours uninterrupted

---

## FAQ

**Q: How many stocks are scanned?**
A: ~6,000 US-listed stocks after filtering

**Q: How long does a full scan take?**
A: 2-3 hours at 1 TPS (1 request/second)

**Q: Can I run it faster?**
A: Yes, but risk rate limiting. Use `--rate-limit 0.5` cautiously.

**Q: What if it's interrupted?**
A: Run `python run_full_market_scan.py --resume` to continue

**Q: How much does this cost?**
A: $0 - Uses free Yahoo Finance API

**Q: Can I run multiple times per day?**
A: Yes, but market data updates once daily

**Q: Does it work on weekends?**
A: Yes, but no new data. Cron scheduled for weekdays only.

**Q: What about pre-market/after-hours?**
A: Run at 6:30 AM EST after overnight data updates

---

## Next Steps

1. ✅ Run test mode: `python run_full_market_scan.py --test-mode`
2. ✅ Review test output
3. ✅ Run full scan: `python run_full_market_scan.py`
4. ✅ Set up cron job for 6:30 AM EST daily
5. ✅ Monitor logs and results

Happy scanning! 📈
```
