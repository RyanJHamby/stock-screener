# Documentation

Extended reference documentation for the Intelligent Stock Screener.

## Setup Guides

- [GitHub Actions Setup](GITHUB_ACTIONS_SETUP.md) — Automate daily scans via GitHub Actions
- [Robinhood Setup](ROBINHOOD_SETUP.md) — Configure read-only position management
- [FMP Integration](SETUP_FMP.md) — Optional Financial Modeling Prep API integration

## Architecture & Design

- [Smart Caching Strategy](SMART_CACHING_STRATEGY.md) — How the Git-based cache reduces API calls by 74%
- [Revised Caching Strategy](REVISED_SMART_CACHING_STRATEGY.md) — Earnings-aware refresh logic
- [Full Market Implementation](FULL_MARKET_IMPLEMENTATION.md) — Scanning 3,800+ stocks at scale
- [Rate Limit Solution](RATE_LIMIT_SOLUTION.md) — Handling yfinance rate limits
- [Detecting Rate Limits](DETECTING_RATE_LIMITS.md) — Diagnosing throttling issues

## Feature Docs

- [Notifications Setup](NOTIFICATIONS_SETUP.md) — Email/Slack alerts configuration
- [Position Automation](POSITION_AUTOMATION.md) — Automated stop-loss reporting
- [Enhanced Fundamentals](ENHANCED_FUNDAMENTALS_USAGE.md) — FMP fundamental data usage
- [Trade Tracking](TRADE_TRACKING_SPREADSHEET.md) — Manual trade log template

## Internal Summaries

- [Project Summary](PROJECT_SUMMARY.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Screening Module Summary](SCREENING_MODULE_SUMMARY.md)
- [Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
