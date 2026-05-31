# Setting Up Daily 6:30 AM EST Cron Job

## Quick Setup

### 1. Open Crontab Editor

```bash
crontab -e
```

This opens your cron configuration in an editor (usually vim or nano).

### 2. Add the Cron Job

Add this line at the end of the file:

```cron
# Daily market scan at 6:30 AM EST (Mon-Fri)
30 6 * * 1-5 /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh
```

**Important**: Replace `/Users/ryanhamby/Documents/stock-screener` with your actual project path!

### 3. Save and Exit

- **vim**: Press `ESC`, then type `:wq` and press `ENTER`
- **nano**: Press `CTRL+X`, then `Y`, then `ENTER`

### 4. Verify Cron Job

```bash
crontab -l
```

You should see your new cron job listed.

---

## Understanding the Cron Syntax

```
30 6 * * 1-5
│  │ │ │ │
│  │ │ │ └─── Day of week (1-5 = Mon-Fri)
│  │ │ └───── Month (1-12, * = every month)
│  │ └─────── Day of month (1-31, * = every day)
│  └───────── Hour (6 = 6 AM)
└──────────── Minute (30 = 30 minutes past the hour)
```

So `30 6 * * 1-5` means:
- **30**: 30 minutes past the hour
- **6**: 6 AM
- **\***: Every day of month
- **\***: Every month
- **1-5**: Monday through Friday only

Result: **6:30 AM EST, Monday-Friday**

---

## Timezone Considerations

### If You're NOT in EST

You need to adjust the hour to match your local time that corresponds to 6:30 AM EST.

**Examples**:

| Your Timezone | Cron Hour | Full Cron |
|---------------|-----------|-----------|
| EST/EDT | 6 | `30 6 * * 1-5` |
| CST/CDT | 5 | `30 5 * * 1-5` |
| MST/MDT | 4 | `30 4 * * 1-5` |
| PST/PDT | 3 | `30 3 * * 1-5` |

**Note**: Cron uses your system's local time.

### Check Your System Timezone

```bash
date +"%Z %z"
```

---

## Testing the Cron Job

### 1. Test the Script Manually First

```bash
cd ~/Documents/stock-screener
./daily_scanner.sh
```

Make sure it runs successfully before setting up cron.

### 2. Test Cron Execution

Set a test cron to run in 2 minutes:

```bash
# Get current time
date

# Edit crontab
crontab -e

# Add a test line (if it's 9:15 AM now, set for 9:17 AM)
17 9 * * * /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh
```

Wait 2 minutes, then check if it ran:

```bash
# Check the log file
ls -lh ./data/logs/
cat ./data/logs/daily_scan_$(date +%Y%m%d).log
```

If it worked, remove the test line and add the real 6:30 AM job.

---

## Monitoring Cron Jobs

### View Cron Logs

**macOS/Linux**:
```bash
# View today's scan log
tail -f ~/Documents/stock-screener/data/logs/daily_scan_$(date +%Y%m%d).log

# List all logs
ls -lh ~/Documents/stock-screener/data/logs/
```

### Check if Cron is Running

```bash
# macOS
sudo launchctl list | grep cron

# Linux
systemctl status cron
```

### Email Notifications (Optional)

To get email when the scan completes, add to `daily_scanner.sh`:

```bash
# At the end of the script
echo "Scan complete. Results in data/daily_scans/latest_scan.txt" | \
  mail -s "Daily Market Scan Complete" your@email.com
```

---

## Common Issues

### Issue: Cron Job Not Running

**Check 1**: Is cron service running?
```bash
# macOS
sudo launchctl list | grep cron

# Linux
systemctl status cron
```

**Check 2**: Are there any syntax errors?
```bash
crontab -l
```

**Check 3**: Check system logs
```bash
# macOS
tail -f /var/log/system.log | grep cron

# Linux
grep CRON /var/log/syslog
```

### Issue: Script Runs But Fails

**Solution**: Check the log file
```bash
cat ~/Documents/stock-screener/data/logs/daily_scan_$(date +%Y%m%d).log
```

Common causes:
- Virtual environment not found (check path in daily_scanner.sh)
- Permissions issue (make sure daily_scanner.sh is executable)
- Missing dependencies (run `pip install -r requirements.txt`)

### Issue: No Output/Logs

**Solution**: Redirect cron output to a file

Change your crontab line to:

```cron
30 6 * * 1-5 /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh >> /tmp/cron_output.log 2>&1
```

Then check `/tmp/cron_output.log` for errors.

---

## Cron Job Management

### List All Cron Jobs

```bash
crontab -l
```

### Edit Cron Jobs

```bash
crontab -e
```

### Remove All Cron Jobs

```bash
crontab -r
```

**WARNING**: This removes ALL your cron jobs, not just this one!

### Disable Temporarily

Comment out the line in crontab:

```cron
# 30 6 * * 1-5 /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh
```

---

## Alternative: Run on Demand

If you don't want to use cron, you can run manually each day:

```bash
cd ~/Documents/stock-screener
./daily_scanner.sh
```

Or create an alias in your `~/.zshrc` or `~/.bashrc`:

```bash
alias market-scan='cd ~/Documents/stock-screener && ./daily_scanner.sh'
```

Then just run:

```bash
market-scan
```

---

## Advanced: Different Schedules

### Run Multiple Times Per Day

```cron
# 6:30 AM and 2:30 PM
30 6,14 * * 1-5 /path/to/daily_scanner.sh
```

### Run Every Hour During Market Hours

```cron
# Every hour from 9 AM to 4 PM
0 9-16 * * 1-5 /path/to/daily_scanner.sh
```

### Run on Specific Days

```cron
# Only on Mondays
30 6 * * 1 /path/to/daily_scanner.sh

# On Mondays and Fridays
30 6 * * 1,5 /path/to/daily_scanner.sh
```

---

## Verifying Setup

### Complete Verification Checklist

- [ ] Script runs manually: `./daily_scanner.sh`
- [ ] Cron job added: `crontab -l` shows the job
- [ ] Correct path in crontab (replace with your actual path)
- [ ] Timezone is correct for your location
- [ ] Script is executable: `ls -l daily_scanner.sh` shows `-rwx`
- [ ] Virtual environment exists: `ls venv/bin/activate`
- [ ] Logs directory exists: `ls data/logs/`
- [ ] Test run completed successfully

### Expected Daily Workflow

1. **6:30 AM EST**: Cron triggers `daily_scanner.sh`
2. **6:30-9:00 AM**: Script runs (2-3 hours for full scan)
3. **9:00 AM**: Scan completes, report saved
4. **Check results**:
   ```bash
   cat ~/Documents/stock-screener/data/daily_scans/latest_scan.txt | less
   ```

---

## Getting Help

If cron isn't working:

1. Check script runs manually first
2. Check cron service is running
3. Check system logs for errors
4. Verify paths are absolute (not relative)
5. Make sure script has execute permissions
6. Check timezone settings

Still having issues? Check the log files:

```bash
# Script logs
ls -lh ~/Documents/stock-screener/data/logs/

# System logs (macOS)
tail -f /var/log/system.log | grep cron

# System logs (Linux)
grep CRON /var/log/syslog
```

---

## Summary

**To set up 6:30 AM EST daily scanning:**

```bash
# 1. Edit crontab
crontab -e

# 2. Add this line (update path!)
30 6 * * 1-5 /Users/ryanhamby/Documents/stock-screener/daily_scanner.sh

# 3. Save and exit

# 4. Verify
crontab -l
```

**To check if it's running:**

```bash
# Check today's log
tail -f ~/Documents/stock-screener/data/logs/daily_scan_$(date +%Y%m%d).log
```

**To view results:**

```bash
cat ~/Documents/stock-screener/data/daily_scans/latest_scan.txt | less
```

That's it! Your system will now automatically scan all US stocks every weekday morning at 6:30 AM EST! 📈
