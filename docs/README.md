# Documentation

Extended reference documentation for the Intelligent Stock Screener.

## About

- [About This Project](ABOUT.md) — What this is and why it was built this way

## Setup Guides

- [GitHub Actions Setup](GITHUB_ACTIONS_SETUP.md) — Automate daily scans via GitHub Actions
- [Cron Job Setup](SETUP_CRON_JOB.md) — Alternative to GitHub Actions: run locally on a schedule
- [Robinhood Setup](ROBINHOOD_SETUP.md) — Configure read-only position management
- [FMP Integration](SETUP_FMP.md) — Optional Financial Modeling Prep API integration

## Architecture & Design

- [Smart Caching Strategy](REVISED_SMART_CACHING_STRATEGY.md) — Git-based storage, earnings-aware refresh, 74% fewer API calls
- [Optimized Scanner](OPTIMIZED_SCANNER_README.md) — Parallel processing design (10-25x faster than the original scanner)
- [Full Market Implementation](FULL_MARKET_IMPLEMENTATION.md) — Scanning 3,800+ stocks at scale
- [Quant Engine](QUANT_ENGINE_README.md) — Phase-based screening engine (`scripts/run_quant_engine.py`)
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
