# Stock Screener - Notifications & Scheduling Setup

Complete guide for setting up automated daily screening with email and Slack notifications.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure notifications
cp .env.example .env
# Edit .env with your email/Slack credentials

# 3. Test configuration
python -m src.notifications.scheduler test

# 4. Run screening once
python -m src.notifications.scheduler run

# 5. Set up automation (choose one):
#    - GitHub Actions (recommended, free)
#    - Cron job (local machine)
#    - AWS Lambda (cloud, ~$1/month)
```

## Email Setup (Gmail)

### Step 1: Enable App Passwords

1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication
3. Go to "App passwords"
4. Generate password for "Mail" app
5. Copy the 16-character password

### Step 2: Configure .env

```bash
EMAIL_FROM=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password
EMAIL_TO=recipient@example.com
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

### Step 3: Test

```bash
python -m src.notifications.scheduler test
```

## Slack Setup (Webhook - Easiest)

### Step 1: Create Webhook

1. Go to https://api.slack.com/messaging/webhooks
2. Click "Create your Slack app"
3. Choose "From scratch"
4. Name it "Stock Screener", select workspace
5. Go to "Incoming Webhooks"
6. Activate and "Add New Webhook to Workspace"
7. Select channel and copy webhook URL

### Step 2: Configure .env

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Step 3: Test

```bash
python -m src.notifications.scheduler test
```

## GitHub Actions Setup (Recommended)

**Benefits:**
- ✅ Free (2,000 minutes/month)
- ✅ No local machine needed
- ✅ Automatic retries
- ✅ Runs on schedule
- ✅ Easy to manage

### Step 1: Add GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions

Add these secrets:
- `EMAIL_FROM`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `SLACK_WEBHOOK_URL` (optional)
- `SCREENING_TICKERS` (optional, defaults provided)

### Step 2: Push Workflow File

The workflow file is already created at `.github/workflows/daily_screening.yml`

```bash
git add .github/workflows/daily_screening.yml
git commit -m "Add automated screening workflow"
git push
```

### Step 3: Configure Schedule

Edit `.github/workflows/daily_screening.yml`:

```yaml
on:
  schedule:
    # Run at 8am EST (13:00 UTC) on weekdays
    - cron: '0 13 * * 1-5'
```

Cron schedule examples:
- `0 13 * * 1-5` = 8am EST, Mon-Fri
- `0 14 * * *` = 9am EST, every day
- `0 9,17 * * 1-5` = 4am and 12pm EST, Mon-Fri

### Step 4: Manual Trigger

You can also trigger manually:
1. Go to Actions tab
2. Click "Daily Stock Screening"
3. Click "Run workflow"

## Cron Job Setup (Local Machine)

**Benefits:**
- ✅ Runs on your machine
- ✅ Full control
- ✅ No external dependencies

### Setup

```bash
# Open crontab editor
crontab -e

# Add this line (8am daily):
0 8 * * * cd /path/to/stock-screener && /path/to/venv/bin/python -m src.notifications.scheduler run >> /path/to/screening.log 2>&1

# Or use absolute paths:
0 8 * * * /Users/you/stock-screener/venv/bin/python -m src.notifications.scheduler run
```

### Verify

```bash
# List cron jobs
crontab -l

# Test run
python -m src.notifications.scheduler run
```

## AWS Lambda Setup (Advanced)

**Benefits:**
- ✅ Runs in cloud
- ✅ Very reliable
- ✅ Auto-scaling
- ✅ ~$1/month cost

### Step 1: Package Code

```bash
# Install dependencies to a directory
pip install -r requirements.txt -t lambda_package/

# Copy your code
cp -r src lambda_package/

# Create ZIP
cd lambda_package && zip -r ../screening_lambda.zip . && cd ..
```

### Step 2: Create Lambda Function

1. Go to AWS Lambda console
2. Create function "stock-screener"
3. Runtime: Python 3.11
4. Upload screening_lambda.zip
5. Set handler: `src.notifications.scheduler.lambda_handler`
6. Set environment variables (EMAIL_FROM, etc.)
7. Increase timeout to 5 minutes
8. Increase memory to 512 MB

### Step 3: Add EventBridge Trigger

1. Add trigger → EventBridge
2. Create new rule
3. Schedule expression: `cron(0 13 ? * MON-FRI *)`
4. Save

## Configuration Options

### Tickers

```bash
# In .env
SCREENING_TICKERS=AAPL,MSFT,GOOGL,AMZN,META,JPM,BAC,WMT

# Or in command line
python -m src.notifications.scheduler run --tickers "AAPL,MSFT,GOOGL"
```

### Top N Results

```bash
# In .env
SCREENING_TOP_N=10

# Or command line
python -m src.notifications.scheduler run --top-n 15
```

### Minimum Signal

```bash
# In .env
SCREENING_MIN_SIGNAL=50  # Only candidates with 50+ signal
```

### Disable Notifications

```bash
# Disable email
python -m src.notifications.scheduler run --no-email

# Disable Slack
python -m src.notifications.scheduler run --no-slack
```

## Email Template Preview

```
Subject: [Stock Screener] Top 10 Candidates - Nov 9, 2024

📊 DAILY STOCK SCREENING RESULTS
November 9, 2024

Summary
47 stocks screened. Top 10 candidates below.

🔥 STRONG BUY (80+) | ✅ BUY (65-79) | ⚡ CONSIDER (50-64)

[HTML TABLE WITH:]
Ticker | Buy Signal | Value | Support | Price | RSI | P/E | P/B

#1 AAPL   85.3        78.5    82.1     $175.50  35.2  28.5  45.3
#2 MSFT   76.2        82.0    68.4     $368.20  42.1  32.1  11.2
...

📈 What These Scores Mean
- Buy Signal: Combined score (70+ is actionable)
- Value Score: Fundamental valuation (80+ is excellent)
- Support Score: Technical setup (80+ is ready to buy)
- RSI: <30 = Oversold (buy opportunity), >70 = Overbought

⚠️ Not financial advice. Always do your own research.
```

## Slack Message Preview

```
📊 Daily Stock Screening Results - November 9, 2024

47 stocks screened. Top 5 candidates below:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#1: AAPL (Apple Inc.)
🔥 STRONG BUY - Buy Signal: 85.3/100
• Value: 78.5 | Support: 82.1
• Price: $175.50 | RSI: 35.2 (Oversold)
• P/E: 28.50 | P/B: 45.30

#2: MSFT (Microsoft Corporation)
✅ BUY - Buy Signal: 76.2/100
• Value: 82.0 | Support: 68.4
• Price: $368.20 | RSI: 42.1 (Neutral)
• P/E: 32.10 | P/B: 11.20

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Legend: 🔥 Strong Buy (80+) | ✅ Buy (65-79) | ⚡ Consider (50-64) | ⏸️ Watch (<50)

⚠️ Not financial advice. Always do your own research.
```

## Troubleshooting

### Email Not Sending

**Issue:** SMTP authentication error
**Solution:** Make sure you're using an app-specific password, not your regular Gmail password

**Issue:** Connection timeout
**Solution:** Check firewall/antivirus isn't blocking port 587

### Slack Not Working

**Issue:** Webhook returns 404
**Solution:** Regenerate webhook URL in Slack settings

**Issue:** "slack-sdk not installed"
**Solution:** `pip install slack-sdk`

### GitHub Actions Failing

**Issue:** Secrets not set
**Solution:** Go to Settings → Secrets and add all required secrets

**Issue:** Running at wrong time
**Solution:** Remember cron uses UTC time. Convert your local time to UTC.

### Cron Job Not Running

**Issue:** Can't find python
**Solution:** Use absolute path: `/path/to/venv/bin/python`

**Issue:** No output
**Solution:** Add logging: `>> /path/to/log.txt 2>&1`

## Testing Commands

```bash
# Test all configuration
python -m src.notifications.scheduler test

# Test email only
python -c "from src.notifications import EmailNotifier; EmailNotifier().test_connection()"

# Test Slack only
python -c "from src.notifications import SlackNotifier; SlackNotifier().test_connection()"

# Run screening without notifications
python -m src.notifications.scheduler run --no-email --no-slack

# Run with specific tickers
python -m src.notifications.scheduler run --tickers "AAPL,MSFT,GOOGL"
```

## Best Practices

1. **Test First**: Always run `test` command before scheduling
2. **Start Small**: Begin with 10-20 tickers, scale up gradually
3. **Monitor Logs**: Check logs regularly for errors
4. **Backup Data**: Database contains historical screening data
5. **Update Tickers**: Review and update ticker list quarterly
6. **Check Limits**: Gmail has sending limits (500/day for free accounts)

## Cost Comparison

| Method | Monthly Cost | Setup Time | Reliability |
|--------|--------------|------------|-------------|
| GitHub Actions | $0 | 10 min | ⭐⭐⭐⭐⭐ |
| Cron Job | $0 | 5 min | ⭐⭐⭐ |
| AWS Lambda | ~$1 | 30 min | ⭐⭐⭐⭐⭐ |

**Recommendation:** Start with GitHub Actions. It's free, reliable, and easy to set up.

## Support

For issues or questions:
1. Check this guide first
2. Test configuration: `python -m src.notifications.scheduler test`
3. Check logs for error messages
4. Review .env file for correct values

## Next Steps

After setup:
1. ✅ Test notifications work
2. ✅ Verify schedule is correct
3. ✅ Monitor first few runs
4. ✅ Adjust ticker list as needed
5. ✅ Customize email/Slack formatting (optional)

Ready to automate your stock screening!
