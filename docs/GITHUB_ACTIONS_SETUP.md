# GitHub Actions Setup Guide

This guide will help you set up automated daily stock screening that runs in the cloud and emails you the results.

## Prerequisites

- GitHub repository for this project
- Gmail account with App Password configured
- The project pushed to GitHub

## Step 1: Push Your Code to GitHub

If you haven't already:

```bash
git add .
git commit -m "Add automated stock screening with GitHub Actions"
git push origin main
```

## Step 2: Configure GitHub Secrets

GitHub secrets keep your sensitive information (like email passwords) secure and encrypted.

1. **Go to your GitHub repository**
   - Navigate to: `https://github.com/YOUR_USERNAME/stock-screener`

2. **Access the Secrets settings**
   - Click `Settings` (top menu)
   - Click `Secrets and variables` → `Actions` (left sidebar)
   - Click `New repository secret` button

3. **Add the following secrets** (click "New repository secret" for each one):

   | Secret Name | Value | Example |
   |------------|-------|---------|
   | `EMAIL_FROM` | Your Gmail address | `ryanhamby22@gmail.com` |
   | `EMAIL_PASSWORD` | Your Gmail App Password | `bufv obel oqqs ujur` |
   | `EMAIL_TO` | Recipient email address | `ryanhamby22@gmail.com` |

   **Optional secrets** (if you want to customize):

   | Secret Name | Value | Default |
   |------------|-------|---------|
   | `SCREENING_TICKERS` | Comma-separated list of tickers | `AAPL,MSFT,GOOGL,AMZN,META,JPM,BAC,WMT,JNJ,XOM` |
   | `SCREENING_TOP_N` | Number of stocks to include in email | `10` |
   | `SCREENING_MIN_SIGNAL` | Minimum buy signal score | `50` |

## Step 3: Test the Workflow

Before waiting for the scheduled run, test it manually:

1. Go to the `Actions` tab in your GitHub repository
2. Click on `Daily Stock Screening Email` workflow (left sidebar)
3. Click `Run workflow` button (right side)
4. Click the green `Run workflow` button in the dropdown
5. Wait for the workflow to complete (usually 1-2 minutes)
6. Check your email inbox!

## Step 4: Configure the Schedule

The workflow is currently set to run at **8:00 AM EST (1:00 PM UTC)** on weekdays.

To change the schedule:

1. Edit `.github/workflows/daily_screening.yml`
2. Modify the cron expression on line 6:

```yaml
schedule:
  # Current: 8am EST (13:00 UTC) on weekdays
  - cron: '0 13 * * 1-5'
```

### Common Cron Schedule Examples

```yaml
# Every day at 9am UTC
- cron: '0 9 * * *'

# Every weekday at 8am EST (13:00 UTC)
- cron: '0 13 * * 1-5'

# Every Monday at 6am EST (11:00 UTC)
- cron: '0 11 * * 1'

# Every day at 8am PST (16:00 UTC)
- cron: '0 16 * * *'
```

**Note**: GitHub Actions uses UTC time. Convert your local time to UTC:
- EST = UTC - 5 hours
- PST = UTC - 8 hours
- Example: 8am EST = 13:00 UTC

## How It Works

1. **Scheduled Trigger**: GitHub Actions runs the workflow at the scheduled time
2. **Fetch Data**: Downloads latest stock data from Yahoo Finance
3. **Screen Stocks**: Analyzes fundamentals and technicals
4. **Send Email**: Sends you an email with the top candidates
5. **Store Artifacts**: Saves database and logs for 7 days (accessible in Actions tab)

## Troubleshooting

### Workflow fails with "Authentication failed"

- Double-check your `EMAIL_FROM` and `EMAIL_PASSWORD` secrets
- Make sure you're using a Gmail App Password, not your regular password
- Verify the App Password doesn't have spaces in GitHub (should be: `bufvobeloqqsujur`)

### No email received

- Check your spam folder
- Check the workflow logs in the Actions tab for errors
- Verify `EMAIL_TO` is set correctly
- Test your email configuration locally first: `python test_email_full.py`

### Workflow doesn't run on schedule

- GitHub Actions may have up to 10-15 minute delays for scheduled workflows
- Free tier has some limitations on concurrent runs
- Check the Actions tab to see if it's queued or disabled

### Want to add Slack notifications?

Set the `SLACK_WEBHOOK_URL` secret with your Slack webhook URL.

## Cost

**Free!** GitHub Actions provides 2,000 minutes/month for free accounts. This workflow uses ~2 minutes per run, so you can run it daily without any cost.

## Support

If you encounter issues:
1. Check the workflow logs in the Actions tab
2. Run the test locally: `python test_email_full.py`
3. Test your setup: `python -m src.notifications.scheduler test`
