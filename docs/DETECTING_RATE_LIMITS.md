# How to Detect Rate Limiting / Throttling

## 🚨 Signs You're Being Throttled

### 1. Error Messages in Logs

**What you'll see**:

```
WARNING - Attempt 1/3 failed for AAPL: HTTPError: 429 Client Error: Too Many Requests
WARNING - Attempt 2/3 failed for MSFT: HTTPError: 429 Client Error: Too Many Requests
ERROR - Failed to fetch GOOGL after 3 attempts
```

**What it means**: Yahoo is rejecting your requests with HTTP 429 "Too Many Requests"

---

### 2. High Error Rate in Progress Output

**Normal progress**:
```
Progress: 1000/3842 (26.0%) | Rate: 24.8/sec | Errors: 0.5% | ETA: 0:11:23
```

**Being throttled**:
```
Progress: 1000/3842 (26.0%) | Rate: 24.8/sec | Errors: 15.3% | ETA: 0:11:23
                                                          ^^^^^ BAD!
```

**What to watch**:
- ✅ **0-2% errors**: Normal, you're fine
- ⚠️ **3-5% errors**: Getting close to limit
- 🚨 **>5% errors**: Being throttled - SLOW DOWN!

---

### 3. Empty/Missing Data for Many Stocks

**What you'll see in logs**:
```
DEBUG - AAPL: Insufficient data (0 days)
DEBUG - MSFT: Insufficient data (0 days)
DEBUG - GOOGL: Insufficient data (0 days)
```

**What it means**: Yahoo is returning empty responses (silent throttling)

---

### 4. Dramatic Slowdown

**Normal**:
```
Progress: 500/3842 (13.0%) | Rate: 24.8/sec | ETA: 0:13:45
Progress: 1000/3842 (26.0%) | Rate: 24.7/sec | ETA: 0:11:23
```

**Being throttled**:
```
Progress: 500/3842 (13.0%) | Rate: 24.8/sec | ETA: 0:13:45
Progress: 1000/3842 (26.0%) | Rate: 8.2/sec | ETA: 0:57:30
                                      ^^^^^ Dropped from 24 to 8!
```

**What it means**: Requests are timing out or delayed significantly

---

### 5. Specific Error Types

#### HTTP 429 Errors
```python
yfinance.exceptions.YFRateLimitError: Too Many Requests
```
**Meaning**: Explicit rate limit hit

#### Connection Timeouts
```python
requests.exceptions.Timeout: Read timeout
```
**Meaning**: Yahoo is delaying responses (soft throttling)

#### Empty Ticker.info
```python
WARNING - Missing data for AAPL: , ,
```
**Meaning**: Yahoo returned empty data (silent throttling)

---

## 📊 Real-Time Monitoring

### Check Logs While Running

**Open a second terminal**:
```bash
# Watch errors in real-time
tail -f ./data/logs/optimized_scan_$(date +%Y%m%d).log | grep -i "error\|warning\|429"
```

**What to look for**:
- Many `WARNING` messages
- `429` errors
- `Too Many Requests`
- `Failed to fetch` messages

### Check Error Rate

The scanner shows this in the progress line:
```
Progress: 1234/3842 (32.1%) | Rate: 23.5/sec | Errors: 2.3% | ETA: 0:09:15
                                                        ^^^^
                                                   Watch this!
```

---

## 🛑 What to Do When Throttled

### Immediate Actions

1. **Stop the scanner**:
   ```bash
   # Press Ctrl+C
   ```

2. **Check the error rate** in the last progress line:
   - If >10%: You're definitely throttled
   - If >5%: Probably throttled

3. **Wait 5-10 minutes**:
   ```bash
   # Let Yahoo's rate limiter reset
   sleep 600  # Wait 10 minutes
   ```

4. **Resume with conservative settings**:
   ```bash
   python run_optimized_scan.py --conservative --resume
   ```

### Step-by-Step Recovery

```bash
# 1. Stop the scan (Ctrl+C)

# 2. Check how many stocks were processed
cat ./data/batch_results/batch_progress.pkl | python -c "
import pickle, sys
with open('./data/batch_results/batch_progress.pkl', 'rb') as f:
    data = pickle.load(f)
print(f'Processed: {len(data[\"processed\"])}/{data[\"total_tickers\"]}')
print(f'Error rate: {data[\"error_rate\"]*100:.1f}%')
"

# 3. Wait 10 minutes
echo "Waiting 10 minutes for rate limit reset..."
sleep 600

# 4. Resume with conservative mode
python run_optimized_scan.py --conservative --resume
```

---

## 🔍 Detailed Error Analysis

### Create Error Report

Add this to your workflow:

```bash
# After scan completes, check error summary
python -c "
import pickle
from pathlib import Path

progress_file = Path('./data/batch_results/batch_progress.pkl')
if progress_file.exists():
    with open(progress_file, 'rb') as f:
        data = pickle.load(f)

    print(f'Total tickers: {data[\"total_tickers\"]}')
    print(f'Processed: {len(data[\"processed\"])}')
    print(f'Error rate: {data[\"error_rate\"]*100:.2f}%')

    if data['error_rate'] > 0.05:
        print('⚠️  HIGH ERROR RATE - You may have been throttled!')
    elif data['error_rate'] > 0.02:
        print('⚠️  Moderate errors - Close to limit')
    else:
        print('✅ Low error rate - All good!')
"
```

### Check for Specific Error Patterns

```bash
# Count 429 errors
grep -c "429" ./data/logs/optimized_scan_$(date +%Y%m%d).log

# Count timeout errors
grep -c -i "timeout" ./data/logs/optimized_scan_$(date +%Y%m%d).log

# Count failed fetches
grep -c "Failed to fetch" ./data/logs/optimized_scan_$(date +%Y%m%d).log
```

---

## 📈 Throttling Patterns

### Early Throttling (First 500 stocks)
```
Progress: 100/3842 (2.6%) | Rate: 24.5/sec | Errors: 0.0%
Progress: 200/3842 (5.2%) | Rate: 24.3/sec | Errors: 8.5%  ← Sudden spike!
Progress: 300/3842 (7.8%) | Rate: 12.1/sec | Errors: 15.2% ← Throttled!
```
**Cause**: Your IP was recently flagged, or you're on a shared network

**Solution**: Use `--conservative` from the start

### Late Throttling (After 2000+ stocks)
```
Progress: 2000/3842 (52.1%) | Rate: 24.8/sec | Errors: 1.2%
Progress: 2500/3842 (65.1%) | Rate: 24.6/sec | Errors: 1.5%
Progress: 3000/3842 (78.1%) | Rate: 15.3/sec | Errors: 7.8%  ← Throttled!
```
**Cause**: Cumulative request count exceeded Yahoo's threshold

**Solution**: Already made good progress, just slow down with `--conservative --resume`

### Gradual Throttling
```
Progress: 1000/3842 (26.0%) | Rate: 24.8/sec | Errors: 1.2%
Progress: 1500/3842 (39.0%) | Rate: 22.1/sec | Errors: 2.8%
Progress: 2000/3842 (52.1%) | Rate: 18.5/sec | Errors: 4.5%
Progress: 2500/3842 (65.1%) | Rate: 14.2/sec | Errors: 6.8%
```
**Cause**: Yahoo is gradually slowing you down (soft throttling)

**Solution**: Stop and resume with `--conservative`

---

## 🎯 Prevention

### Pre-Flight Check

Before running a full scan:

```bash
# 1. Test with 100 stocks
python run_optimized_scan.py --test-mode

# 2. Check error rate in output
# If errors >2%, use conservative mode

# 3. Full scan with appropriate settings
python run_optimized_scan.py  # or --conservative
```

### Best Practices

1. **Start conservative on first run of the day**
   ```bash
   python run_optimized_scan.py --conservative
   ```

2. **Run during off-peak hours**
   - ✅ Best: 2-6 AM EST (low Yahoo traffic)
   - ✅ Good: 8 PM - midnight EST
   - ⚠️ Risky: 9-11 AM EST (market open, high traffic)

3. **Don't run back-to-back scans**
   - Wait 30+ minutes between full scans
   - Yahoo may flag rapid repeated scans

4. **Monitor the first 500 stocks**
   - If error rate >3% in first 500, stop and use `--conservative`

---

## 🚦 Traffic Light System

### Green Light ✅ (Keep Going)
- Error rate: 0-2%
- Rate: Steady (24-25 TPS)
- No 429 errors
- No timeout warnings

**Action**: Continue as normal

### Yellow Light ⚠️ (Caution)
- Error rate: 3-5%
- Rate: Dropping slightly (20-23 TPS)
- Occasional 429 errors (<1% of requests)
- Some timeout warnings

**Action**:
- Monitor closely
- Consider stopping and resuming with `--conservative`
- Don't increase speed

### Red Light 🛑 (Stop!)
- Error rate: >5%
- Rate: Dropping significantly (<20 TPS)
- Frequent 429 errors (>1% of requests)
- Many timeout warnings
- Many "Failed to fetch" messages

**Action**:
1. Stop immediately (Ctrl+C)
2. Wait 10 minutes
3. Resume with `--conservative`

---

## 🔧 Automated Detection Script

Create `check_throttling.sh`:

```bash
#!/bin/bash
# Check if you're being throttled

LOG_FILE="./data/logs/optimized_scan_$(date +%Y%m%d).log"

if [ ! -f "$LOG_FILE" ]; then
    echo "No log file found for today"
    exit 0
fi

echo "Throttling Detection Report"
echo "============================"

# Count errors
ERROR_429=$(grep -c "429" "$LOG_FILE" 2>/dev/null || echo "0")
TIMEOUTS=$(grep -c -i "timeout" "$LOG_FILE" 2>/dev/null || echo "0")
FAILED=$(grep -c "Failed to fetch" "$LOG_FILE" 2>/dev/null || echo "0")

echo "429 Errors: $ERROR_429"
echo "Timeouts: $TIMEOUTS"
echo "Failed Fetches: $FAILED"

TOTAL_ERRORS=$((ERROR_429 + TIMEOUTS + FAILED))

if [ $TOTAL_ERRORS -gt 100 ]; then
    echo ""
    echo "🚨 HIGH ERROR COUNT - You are likely being throttled!"
    echo "   Recommendation: Stop and use --conservative mode"
elif [ $TOTAL_ERRORS -gt 50 ]; then
    echo ""
    echo "⚠️  Moderate errors - Approaching throttle limit"
    echo "   Recommendation: Monitor closely or switch to --conservative"
else
    echo ""
    echo "✅ Low error count - Operating normally"
fi
```

Usage:
```bash
chmod +x check_throttling.sh
./check_throttling.sh
```

---

## 📋 Quick Reference

### Throttling Indicators

| Indicator | Normal | Throttled |
|-----------|--------|-----------|
| Error Rate | 0-2% | >5% |
| Rate (TPS) | 23-25 | <20 or dropping |
| 429 Errors | 0-10 total | >50 total |
| Timeouts | Rare | Frequent |
| Empty Data | <1% | >3% |

### Response Times

**Stop immediately if you see**:
- Error rate jumps above 10%
- More than 50 429 errors in a row
- Rate drops below 15 TPS
- Many stocks showing "0 days" of data

**Resume after**:
- Waiting 10 minutes
- Using `--conservative` flag
- Monitoring error rate closely

---

## Summary

**You'll know you're throttled when**:

1. ✅ **Error rate >5%** in progress output (most reliable)
2. ✅ **Lots of 429 errors** in logs
3. ✅ **Rate drops significantly** (24 → 15 TPS)
4. ✅ **Many stocks return empty data**
5. ✅ **Timeout errors** become frequent

**What to do**:
1. Stop (Ctrl+C)
2. Wait 10 minutes
3. Resume with `--conservative`
4. Check error rate - should be <2%

**Monitor in real-time**:
```bash
# Watch the "Errors" percentage in the progress line
Progress: 1234/3842 (32.1%) | Rate: 23.5/sec | Errors: 2.3% | ETA: 0:09:15
                                                        ^^^^
                                                   Keep this <5%
```

That's it! The system makes it very clear when you're being throttled. Just watch the error percentage! 📊
