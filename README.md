# Stock Screener

A daily US stock screener that automates Mark Minervini's published Trend Template. It finds Phase 2 uptrends, checks relative strength against SPY and a fundamentals screen, then proposes a stop loss and risk/reward for each buy signal. The method is Minervini's, not mine; see [Credit](#credit).

[![Tests](https://github.com/RyanJHamby/stock-screener/actions/workflows/tests.yml/badge.svg)](https://github.com/RyanJHamby/stock-screener/actions/workflows/tests.yml)
[![Daily Scan](https://github.com/RyanJHamby/stock-screener/actions/workflows/daily_screening_git_storage.yml/badge.svg)](https://github.com/RyanJHamby/stock-screener/actions/workflows/daily_screening_git_storage.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![Example scan output showing benchmark summary, market breadth, and top buy signals](assets/example-output.png)

Not financial advice. See the [disclaimer](#disclaimer).

## Try it

```bash
pip install -r requirements.txt
just scan-test      # small scan; needs network access
```

## What it does

- Fetches the NASDAQ/NYSE universe and one year of daily prices (yfinance).
- Classifies each stock into one of four trend phases and scores relative strength against SPY.
- Scores fundamentals (revenue, EPS, inventory) for Phase 1 and 2 stocks.
- Emits ranked buy and sell signals, with a stop loss and risk/reward for each buy.
- Only emits buy signals when the market itself is healthy (SPY phase and breadth).
- Runs on GitHub Actions each weekday and commits the report to `data/daily_scans/`.
- Optionally reads Robinhood positions (read-only) and recommends trailing stops.

## Quick start

Requires Python 3.12+.

```bash
git clone https://github.com/RyanJHamby/stock-screener.git
cd stock-screener
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; every setting in it is off by default
just setup-check              # shows what is configured
just scan-test                # small test-mode scan
just scan                     # full market scan, conservative rate limits
just dashboard                # local dashboard on port 5050
```

Without `just`, the recipes are in the [justfile](justfile). Reports are written to
`data/daily_scans/`; the newest is `latest_optimized_scan.txt`.

Run the tests with `pytest tests/ --ignore=tests/test_email_full.py`.

## How it works

```mermaid
graph LR
    U[Universe<br/>NASDAQ and NYSE] --> P[Prices<br/>1 year daily]
    P --> F[Fundamentals<br/>Git-stored cache]
    F --> C[Phase classifier]
    F --> R[Relative strength vs SPY]
    F --> Q[Fundamental score]
    C --> S[Signal engine]
    R --> S
    Q --> S
    S --> B[Buy signals<br/>stop loss and R/R]
    S --> L[Sell signals]
    B --> O[Daily report]
    L --> O
```

A buy signal requires a Phase 2 stock that passes 7 of Minervini's 8 Trend Template criteria:

1. Price above the 150 and 200 SMA
2. 150 SMA above the 200 SMA
3. 200 SMA rising for at least a month
4. 50 SMA above 150 SMA above 200 SMA
5. Price above the 50 SMA
6. Price at least 30% above the 52-week low
7. Price within 25% of the 52-week high
8. Relative strength slope of +0.15 or more

Details: [methodology](docs/METHODOLOGY.md), [scoring and stop loss](docs/TECHNICAL_DETAILS.md), [position management](docs/POSITION_MANAGEMENT.md), [roadmap ideas](docs/ROADMAP.md).

## Results

Taken from the 49 scan reports in `data/daily_scans/` (2026-09-01 to 2026-11-06), which ran on GitHub Actions:

| Measure | Range across reports |
|---|---|
| Universe size | 3,753 to 3,773 stocks |
| Stocks analyzed per run | 1,624 to 1,846 |
| Processing time | 62.6 to 62.9 minutes |
| Error rate | 3.4% to 8.8% |

Only about half the universe is analyzed on a given run. These figures are read from the saved reports, not from a benchmark run on named hardware. There is no backtest, so nothing here says whether the signals make money.

## Configuration

All optional, set in `.env` (see [.env.example](.env.example)):

| Setting | Purpose |
|---|---|
| `DATABASE_URL` | Database for stored results |
| `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_TO`, `EMAIL_SMTP_*` | Email notifications |
| `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` | Slack notifications |
| `FMP_API_KEY` | Financial Modeling Prep fundamentals ([setup](docs/SETUP_FMP.md)) |
| `ROBINHOOD_USERNAME` | Read-only position tracking; the password is prompted, never stored |

## Credit

The ideas here are not mine.

- **Mark Minervini**: the Trend Template, the Stage 2 buy criteria, pivot-point entries and the risk approach, from *Trade Like a Stock Market Wizard* (2013) and *Think & Trade Like a Champion* (2017).
- **Stan Weinstein**: the four-stage market cycle behind the phase classification (*Secrets for Profiting in Bull and Bear Markets*).
- **William O'Neil and IBD**: the growth-fundamentals screen (CANSLIM) and relative strength ranking.

What is mine is the code that tries to automate those published criteria. I am not affiliated with or endorsed by any of these authors, and my version is an interpretation that differs in places. For example, the relative strength check uses a slope threshold where Minervini uses an RS rank. Read the books for the real method. More in [methodology](docs/METHODOLOGY.md).

## How this was built

I wrote this project with AI coding assistants. Claude Code agents opened some pull requests on `agent/*` branches, which I reviewed and merged. The signal logic follows Minervini's published method; the tests and the daily scan reports are the evidence of what it does.

## Disclaimer

For educational and informational purposes only. Not financial advice. Past performance does not guarantee future results, and trading involves risk of loss. The author is not responsible for losses from using this software.

## License

MIT. See [LICENSE](LICENSE). Contributions: see [CONTRIBUTING.md](CONTRIBUTING.md).
