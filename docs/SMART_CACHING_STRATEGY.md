# Smart Caching Strategy for GitHub Actions

## Problem Statement

Running daily scans in GitHub Actions with these constraints:
1. **GitHub Actions**: Ephemeral environment (no persistent storage between runs)
2. **Rate Limiting**: Yahoo Finance throttles after ~2,000 calls/hour
3. **Data Freshness**: Need daily price updates
4. **Fundamental Updates**: Only refresh when earnings are reported (quarterly)
5. **3,800 stocks**: 15,200 API calls currently (too many!)

## Solution: Three-Tier Smart Caching

### Tier 1: GitHub Actions Cache (Persistent Across Runs)

GitHub Actions provides a cache API that persists between workflow runs for up to 7 days.

**What to cache:**
- Price history (yesterday's data)
- Fundamental data (quarterly, rarely changes)
- Stock universe list

**How it works:**
```yaml
- name: Cache stock data
  uses: actions/cache@v4
  with:
    path: |
      data/cache/
      data/price_history/
      data/fundamentals/
    key: stock-data-${{ hashFiles('data/universe.json') }}-${{ steps.date.outputs.date }}
    restore-keys: |
      stock-data-${{ hashFiles('data/universe.json') }}-
      stock-data-
```

**Benefits:**
- ✓ Reuse yesterday's price history
- ✓ Only fetch TODAY'S price for each stock
- ✓ Fundamentals cached until earnings season

### Tier 2: Incremental Price Updates (Fetch Only New Data)

Instead of fetching 250 days every time, fetch incrementally:

**Day 1 (Monday):**
```python
# No cache - fetch full 1y history
price_data = fetcher.fetch_price_history(ticker, period='1y')  # 250 days
save_to_cache(ticker, price_data)
```

**Day 2 (Tuesday):**
```python
# Load yesterday's cache
cached_data = load_from_cache(ticker)  # 250 days (Mon-249 days ago)

# Fetch only latest 2 days
new_data = fetcher.fetch_price_history(ticker, period='5d')  # 5 days

# Merge: keep 249 old days + add new day
merged_data = merge_and_trim(cached_data, new_data, keep_days=250)
save_to_cache(ticker, merged_data)
```

**API calls saved:**
- Before: 3,800 stocks × 250 days = 950,000 data points daily
- After: 3,800 stocks × 5 days = 19,000 data points daily
- **Savings: 98% less data transfer!**

### Tier 3: Earnings-Aware Fundamental Refresh

Fundamentals only change when companies report earnings (quarterly).

**Earnings Season Schedule:**
- Q4 Earnings: Jan 15 - Feb 15 (FY 2024 reports)
- Q1 Earnings: Apr 15 - May 15
- Q2 Earnings: Jul 15 - Aug 15
- Q3 Earnings: Oct 15 - Nov 15

**Smart refresh logic:**
```python
def should_refresh_fundamentals(ticker, last_fetch_date):
    """Only refresh if:
    1. Never fetched before, OR
    2. During earnings season AND >7 days since last fetch, OR
    3. Outside earnings season AND >90 days since last fetch
    """
    if last_fetch_date is None:
        return True

    days_since = (datetime.now() - last_fetch_date).days

    if is_earnings_season():
        # During earnings: refresh weekly
        return days_since >= 7
    else:
        # Outside earnings: refresh quarterly
        return days_since >= 90
```

**API calls saved:**
- Before: 3,800 stocks × 3 fundamental calls = 11,400 calls daily
- After (earnings season): ~543 stocks/day × 3 = 1,629 calls
- After (non-earnings): ~42 stocks/day × 3 = 126 calls
- **Savings: 86-99% fewer fundamental calls!**

## Complete Daily Workflow

### GitHub Actions Workflow (Optimized)

```yaml
name: Daily Stock Screening

on:
  schedule:
    - cron: '0 13 * * 1-5'  # 8am EST weekdays
  workflow_dispatch:

jobs:
  screen-stocks:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Get current date
        id: date
        run: echo "date=$(date +'%Y-%m-%d')" >> $GITHUB_OUTPUT

      - name: Restore stock data cache
        id: cache-restore
        uses: actions/cache/restore@v4
        with:
          path: |
            data/cache/
            data/price_history/
            data/fundamentals/
          key: stock-data-${{ steps.date.outputs.date }}
          restore-keys: |
            stock-data-

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run incremental stock screening
        env:
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          CACHE_HIT: ${{ steps.cache-restore.outputs.cache-hit }}
        run: |
          python run_optimized_scan.py --incremental --conservative

      - name: Save stock data cache
        uses: actions/cache/save@v4
        if: always()
        with:
          path: |
            data/cache/
            data/price_history/
            data/fundamentals/
          key: stock-data-${{ steps.date.outputs.date }}

      - name: Upload screening results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: screening-results-${{ github.run_number }}
          path: |
            data/daily_scans/latest_optimized_scan.txt
            data/logs/*.log
          retention-days: 7
```

## Implementation: Smart Data Fetcher

### New: `src/data/smart_fetcher.py`

```python
"""Smart data fetcher with incremental updates and earnings-aware caching."""

import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class SmartDataFetcher:
    """Fetches data intelligently with incremental updates and smart caching."""

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Separate subdirectories
        self.price_cache_dir = self.cache_dir / "price_history"
        self.fundamental_cache_dir = self.cache_dir / "fundamentals"
        self.price_cache_dir.mkdir(exist_ok=True)
        self.fundamental_cache_dir.mkdir(exist_ok=True)

    def fetch_price_incremental(self, ticker: str, required_days: int = 250) -> pd.DataFrame:
        """Fetch price data incrementally.

        - If cache exists and is recent: fetch only last 5 days and merge
        - If cache is old or missing: fetch full period

        Args:
            ticker: Stock ticker
            required_days: Number of days needed for indicators (default 250 for 200 SMA)

        Returns:
            DataFrame with required_days of price data
        """
        cache_path = self.price_cache_dir / f"{ticker}_prices.pkl"
        cache_meta_path = self.price_cache_dir / f"{ticker}_prices_meta.pkl"

        # Try to load cached data
        cached_data = None
        cache_date = None

        if cache_path.exists() and cache_meta_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                with open(cache_meta_path, 'rb') as f:
                    cache_meta = pickle.load(f)
                    cache_date = cache_meta.get('last_updated')

                logger.info(f"{ticker}: Found cached data from {cache_date}")
            except Exception as e:
                logger.warning(f"{ticker}: Failed to load cache: {e}")
                cached_data = None

        # Determine if we can do incremental update
        can_increment = False
        if cached_data is not None and cache_date is not None:
            days_old = (datetime.now() - cache_date).days
            if days_old <= 5 and len(cached_data) >= required_days - 10:
                can_increment = True

        if can_increment:
            # INCREMENTAL UPDATE - fetch only recent data
            logger.info(f"{ticker}: Incremental update (cache {days_old} days old)")

            try:
                stock = yf.Ticker(ticker)
                # Fetch last 5 days to ensure we have overlap
                new_data = stock.history(period='5d', interval='1d')

                if not new_data.empty:
                    # Merge: combine cached + new, remove duplicates, keep latest required_days
                    merged = self._merge_price_data(cached_data, new_data, required_days)

                    # Save updated cache
                    self._save_price_cache(ticker, merged)

                    logger.info(f"{ticker}: Incremental update successful ({len(merged)} days)")
                    return merged
                else:
                    logger.warning(f"{ticker}: Incremental fetch returned no data, using cache")
                    return cached_data

            except Exception as e:
                logger.error(f"{ticker}: Incremental update failed: {e}, using cache")
                return cached_data

        else:
            # FULL FETCH - no cache or cache too old
            logger.info(f"{ticker}: Full fetch (no cache or cache too old)")

            try:
                stock = yf.Ticker(ticker)
                # Fetch 1 year of data (250 trading days)
                data = stock.history(period='1y', interval='1d')

                if not data.empty:
                    # Save to cache
                    self._save_price_cache(ticker, data)
                    logger.info(f"{ticker}: Full fetch successful ({len(data)} days)")
                    return data
                else:
                    logger.warning(f"{ticker}: Full fetch returned no data")
                    return pd.DataFrame()

            except Exception as e:
                logger.error(f"{ticker}: Full fetch failed: {e}")
                return pd.DataFrame()

    def fetch_fundamentals_smart(self, ticker: str) -> Dict:
        """Fetch fundamentals with earnings-aware caching.

        Only refreshes:
        - During earnings season: if >7 days old
        - Outside earnings season: if >90 days old

        Returns:
            Dict with quarterly fundamental data
        """
        cache_path = self.fundamental_cache_dir / f"{ticker}_fundamentals.pkl"

        # Check if we need to refresh
        should_refresh = self._should_refresh_fundamentals(cache_path)

        if not should_refresh and cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached = pickle.load(f)
                logger.info(f"{ticker}: Using cached fundamentals")
                return cached
            except Exception as e:
                logger.warning(f"{ticker}: Cache load failed: {e}, refreshing")

        # Fetch fresh fundamentals
        logger.info(f"{ticker}: Fetching fresh fundamentals")

        try:
            from .fundamentals_fetcher import fetch_quarterly_financials
            data = fetch_quarterly_financials(ticker)

            if data:
                # Save to cache with timestamp
                with open(cache_path, 'wb') as f:
                    pickle.dump({
                        'data': data,
                        'fetched_at': datetime.now()
                    }, f)

                return data
            else:
                return {}

        except Exception as e:
            logger.error(f"{ticker}: Fundamental fetch failed: {e}")
            return {}

    def _merge_price_data(self, old_data: pd.DataFrame, new_data: pd.DataFrame,
                          keep_days: int) -> pd.DataFrame:
        """Merge old and new price data, keeping only keep_days most recent."""

        # Ensure both have Date column
        if 'Date' not in old_data.columns and old_data.index.name == 'Date':
            old_data = old_data.reset_index()
        if 'Date' not in new_data.columns and new_data.index.name == 'Date':
            new_data = new_data.reset_index()

        # Combine
        combined = pd.concat([old_data, new_data], ignore_index=True)

        # Remove duplicates (keep latest)
        combined['Date'] = pd.to_datetime(combined['Date'])
        combined = combined.sort_values('Date')
        combined = combined.drop_duplicates(subset=['Date'], keep='last')

        # Keep only most recent keep_days
        if len(combined) > keep_days:
            combined = combined.iloc[-keep_days:]

        return combined.reset_index(drop=True)

    def _save_price_cache(self, ticker: str, data: pd.DataFrame):
        """Save price data and metadata to cache."""
        cache_path = self.price_cache_dir / f"{ticker}_prices.pkl"
        cache_meta_path = self.price_cache_dir / f"{ticker}_prices_meta.pkl"

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

            meta = {
                'last_updated': datetime.now(),
                'num_days': len(data)
            }
            with open(cache_meta_path, 'wb') as f:
                pickle.dump(meta, f)

        except Exception as e:
            logger.warning(f"{ticker}: Failed to save cache: {e}")

    def _should_refresh_fundamentals(self, cache_path: Path) -> bool:
        """Determine if fundamentals should be refreshed."""

        if not cache_path.exists():
            return True

        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
                fetched_at = cached.get('fetched_at')

            if fetched_at is None:
                return True

            days_old = (datetime.now() - fetched_at).days

            if self._is_earnings_season():
                # During earnings season: refresh weekly
                return days_old >= 7
            else:
                # Outside earnings season: refresh quarterly
                return days_old >= 90

        except Exception as e:
            logger.warning(f"Cache check failed: {e}, will refresh")
            return True

    def _is_earnings_season(self) -> bool:
        """Check if currently in earnings season.

        Earnings seasons:
        - Q4: Jan 15 - Feb 15
        - Q1: Apr 15 - May 15
        - Q2: Jul 15 - Aug 15
        - Q3: Oct 15 - Nov 15
        """
        now = datetime.now()
        month = now.month
        day = now.day

        earnings_windows = [
            (1, 15, 2, 15),   # Q4 earnings
            (4, 15, 5, 15),   # Q1 earnings
            (7, 15, 8, 15),   # Q2 earnings
            (10, 15, 11, 15)  # Q3 earnings
        ]

        for start_month, start_day, end_month, end_day in earnings_windows:
            if start_month == end_month:
                if month == start_month and start_day <= day <= end_day:
                    return True
            else:
                if (month == start_month and day >= start_day) or \
                   (month == end_month and day <= end_day):
                    return True

        return False
```

## Expected Results

### API Call Reduction

| Scenario | Current | With Smart Caching | Savings |
|----------|---------|-------------------|---------|
| **Price Data** (daily) | 3,800 stocks × 250 days | 3,800 stocks × 5 days | **98%** ↓ |
| **Fundamentals** (earnings season) | 3,800 × 3 calls | ~543 × 3 calls | **86%** ↓ |
| **Fundamentals** (non-earnings) | 3,800 × 3 calls | ~42 × 3 calls | **99%** ↓ |
| **Total API calls/day** | 15,200 | 560-1,600 | **89-96%** ↓ |

### Daily Workflow

**Monday (no cache):**
- Full fetch: 15,200 calls
- Cache saved to GitHub Actions

**Tuesday-Friday (cache hits):**
- Incremental price: 3,800 calls (5d each)
- Smart fundamentals: 126-1,629 calls
- Total: 3,926-5,429 calls
- **73-96% fewer calls!**

### Rate Limit Safety

With conservative mode (2 workers, 1s delay):
- Before: 253 calls/min → **THROTTLED** ⚠️
- After: 15-25 calls/min → **SAFE** ✓✓

## Sources

- [Yahoo Finance Earnings Calendar](https://finance.yahoo.com/calendar/earnings)
- [Nasdaq Earnings Calendar](https://www.nasdaq.com/market-activity/earnings)
- [Trading Economics Earnings Calendar](https://tradingeconomics.com/earnings-calendar)
- [eToro Guide to Fiscal Quarters](https://www.etoro.com/investing/financial-years-fiscal-quarters/)
