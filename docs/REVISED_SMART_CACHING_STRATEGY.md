# Revised Smart Caching Strategy - Optimized for Your Requirements

## Your Actual Requirements (Clarified)

1. **Price Data**: Refresh ALL stocks EVERY day (always fresh, no caching)
2. **Fundamental Data**: Cache for 90+ days (persist beyond GitHub Actions limits)
3. **GitHub Actions**: Must work across workflow runs
4. **Rate Limiting**: Stay under Yahoo Finance limits

## The Problem with Previous Approach

- ❌ GitHub Actions **cache**: Only 7 days retention
- ❌ GitHub Actions **artifacts**: Can't access across different workflow runs
- ❌ Tried to cache price data: You want fresh daily prices!

## ✅ New Solution: Git-Based Persistent Storage + Smart Fetching

### Core Strategy

1. **Price Data**: ALWAYS fetch fresh (but optimize to 1 year not 2 years)
2. **Fundamental Data**: Store in Git repository, persist 90+ days
3. **Earnings-Aware**: Only refresh fundamentals during earnings season

### Why This Works

**Git Repository Storage:**
- ✅ Unlimited retention (not 7 days)
- ✅ Accessible across all workflow runs
- ✅ Free (no external storage costs)
- ✅ Version controlled (can track changes)
- ✅ Automatic with GitHub Actions

**Small Storage Footprint:**
- Fundamental data per stock: ~5 KB
- 3,800 stocks × 5 KB = **19 MB total**
- Git handles this easily

## Implementation

### 1. Price Data Strategy (ALWAYS FRESH)

**No caching - fetch every day:**
```python
def fetch_price_daily(ticker: str) -> pd.DataFrame:
    """Fetch 1 year of price data (no caching).

    This ensures:
    - Latest prices always included
    - 250 days for 200-day SMA
    - Fresh data every run
    """
    stock = yf.Ticker(ticker)
    # Fetch 1 year (not 2 years - 50% less data)
    data = stock.history(period='1y', interval='1d')
    return data
```

**API calls:**
- 3,800 stocks × 1 call each = **3,800 calls**
- Data points: 3,800 × 250 days = 950,000 points
- With conservative mode (2 workers, 1s delay): ~32 minutes

### 2. Fundamental Data Strategy (GIT STORAGE)

**Store fundamentals in Git repository:**
```
data/
  fundamentals_cache/
    AAPL_fundamentals.json      # Last updated: 2025-01-20
    MSFT_fundamentals.json      # Last updated: 2025-01-18
    GOOGL_fundamentals.json     # Last updated: 2024-11-15
    ...
    metadata.json               # Tracks last update per stock
```

**Earnings-aware refresh logic:**

```python
def should_refresh_fundamental(ticker: str) -> bool:
    """Determine if fundamental data needs refresh.

    Refresh when:
    1. Never fetched before, OR
    2. During earnings season AND >7 days old, OR
    3. Data >90 days old (stale even outside earnings)
    """
    metadata = load_metadata()
    last_update = metadata.get(ticker, {}).get('last_updated')

    if last_update is None:
        return True  # Never fetched

    days_old = (datetime.now() - last_update).days

    if days_old > 90:
        return True  # Stale data

    if is_earnings_season() and days_old >= 7:
        return True  # Earnings season - weekly refresh

    return False  # Use cached data
```

**Daily fundamental refresh:**
- **Outside earnings** (~9 months/year): ~42 stocks/day (3,800 ÷ 90)
- **During earnings** (~3 months/year): ~543 stocks/day (3,800 ÷ 7)
- **API calls**: 42-543 stocks × 3 calls = **126-1,629 calls/day**

### 3. GitHub Actions Workflow (Git-Based Storage)

```yaml
name: Daily Stock Screening (Git-Based Storage)

on:
  schedule:
    - cron: '0 13 * * 1-5'
  workflow_dispatch:

jobs:
  screen-stocks:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Check existing fundamental cache
        run: |
          if [ -d "data/fundamentals_cache" ]; then
            echo "✓ Found existing fundamental cache"
            echo "Cached stocks: $(ls data/fundamentals_cache/*.json 2>/dev/null | wc -l)"
          else
            echo "⚠ No existing cache, will create"
            mkdir -p data/fundamentals_cache
          fi

      - name: Run optimized stock screening
        env:
          EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          EMAIL_SMTP_SERVER: ${{ secrets.EMAIL_SMTP_SERVER || 'smtp.gmail.com' }}
          EMAIL_SMTP_PORT: ${{ secrets.EMAIL_SMTP_PORT || '587' }}
        run: |
          # Conservative mode to avoid rate limits
          # Fresh prices daily, smart fundamental refresh
          python run_optimized_scan.py --conservative --git-storage

      - name: Commit updated fundamental cache
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"

          # Add only fundamental cache (not price data)
          git add data/fundamentals_cache/

          # Commit if there are changes
          git diff --staged --quiet || git commit -m "Update fundamental cache - $(date +'%Y-%m-%d')"

      - name: Push changes
        uses: ad-m/github-push-action@v0.8.0
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          branch: main

      - name: Upload screening results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: screening-results-${{ github.run_number }}
          path: |
            data/daily_scans/latest_optimized_scan.txt
            data/logs/*.log
          retention-days: 30
```

### 4. Updated Smart Fetcher

**File: `src/data/git_storage_fetcher.py`**

```python
"""Smart fetcher using Git-based storage for fundamentals."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class GitStorageFetcher:
    """Fetcher with Git-based fundamental storage and fresh price data."""

    def __init__(self, fundamentals_dir: str = "./data/fundamentals_cache"):
        """Initialize fetcher.

        Args:
            fundamentals_dir: Directory for fundamental storage (in Git)
        """
        self.fundamentals_dir = Path(fundamentals_dir)
        self.fundamentals_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.fundamentals_dir / "metadata.json"
        logger.info(f"GitStorageFetcher initialized: {fundamentals_dir}")

    def fetch_price_fresh(self, ticker: str) -> pd.DataFrame:
        """Fetch fresh price data (1 year, no caching).

        Always fetches latest data to ensure current prices.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with ~250 days of price data
        """
        try:
            stock = yf.Ticker(ticker)
            # Always fetch 1 year (250 trading days)
            data = stock.history(period='1y', interval='1d')

            if not data.empty:
                logger.debug(f"{ticker}: Fetched {len(data)} days (fresh)")
                return data
            else:
                logger.warning(f"{ticker}: No price data returned")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"{ticker}: Price fetch failed: {e}")
            return pd.DataFrame()

    def fetch_fundamentals_smart(self, ticker: str) -> Dict:
        """Fetch fundamentals with Git-based caching.

        Uses earnings-aware refresh:
        - During earnings season: refresh if >7 days old
        - Outside earnings: refresh if >90 days old

        Args:
            ticker: Stock ticker

        Returns:
            Dict with fundamental data
        """
        fundamental_file = self.fundamentals_dir / f"{ticker}_fundamentals.json"

        # Check if refresh needed
        should_refresh = self._should_refresh_fundamental(ticker, fundamental_file)

        if not should_refresh and fundamental_file.exists():
            # Load from Git storage
            try:
                with open(fundamental_file, 'r') as f:
                    cached = json.load(f)
                logger.debug(f"{ticker}: Using cached fundamentals")
                return cached.get('data', {})
            except Exception as e:
                logger.warning(f"{ticker}: Cache load failed: {e}, will refresh")

        # Fetch fresh fundamentals
        logger.info(f"{ticker}: Fetching fresh fundamentals")

        try:
            from .fundamentals_fetcher import fetch_quarterly_financials
            data = fetch_quarterly_financials(ticker)

            if data:
                # Save to Git storage
                cache_data = {
                    'data': data,
                    'fetched_at': datetime.now().isoformat()
                }

                with open(fundamental_file, 'w') as f:
                    json.dump(cache_data, f, indent=2, default=str)

                # Update metadata
                self._update_metadata(ticker)

                return data
            else:
                return {}

        except Exception as e:
            logger.error(f"{ticker}: Fundamental fetch failed: {e}")
            return {}

    def _should_refresh_fundamental(self, ticker: str, file_path: Path) -> bool:
        """Check if fundamental needs refresh."""

        if not file_path.exists():
            return True

        try:
            with open(file_path, 'r') as f:
                cached = json.load(f)
                fetched_at_str = cached.get('fetched_at')

            if fetched_at_str is None:
                return True

            fetched_at = datetime.fromisoformat(fetched_at_str)
            days_old = (datetime.now() - fetched_at).days

            # Always refresh if >90 days old
            if days_old > 90:
                logger.info(f"{ticker}: Stale data ({days_old} days), refreshing")
                return True

            # During earnings season: refresh weekly
            if self._is_earnings_season() and days_old >= 7:
                logger.info(f"{ticker}: Earnings season refresh ({days_old} days old)")
                return True

            return False

        except Exception as e:
            logger.warning(f"{ticker}: Error checking cache: {e}, will refresh")
            return True

    def _is_earnings_season(self) -> bool:
        """Check if in earnings season."""
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

    def _update_metadata(self, ticker: str):
        """Update metadata tracking."""
        metadata = {}

        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    metadata = json.load(f)
            except Exception:
                pass

        metadata[ticker] = {
            'last_updated': datetime.now().isoformat(),
            'in_earnings_season': self._is_earnings_season()
        }

        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        cached_files = list(self.fundamentals_dir.glob("*_fundamentals.json"))

        stats = {
            'cached_stocks': len(cached_files),
            'in_earnings_season': self._is_earnings_season(),
            'storage_dir': str(self.fundamentals_dir)
        }

        return stats
```

## Expected Performance

### Daily API Calls

| Component | Calls | Notes |
|-----------|-------|-------|
| **Price Data** (fresh daily) | 3,800 | 1 year history each |
| **Fundamentals** (earnings season) | 1,629 | ~543 stocks × 3 calls |
| **Fundamentals** (normal) | 126 | ~42 stocks × 3 calls |
| **Total (earnings season)** | **5,429** | Down from 15,200! |
| **Total (normal)** | **3,926** | Down from 15,200! |

### Rate Limit Safety

With conservative mode (2 workers, 1s delay = ~2 TPS):
- **5,429 calls** ÷ 2 TPS = ~45 minutes
- **Calls per minute**: ~121 (well under ~200 limit)
- **Risk**: ✓ LOW (was HIGH)

### Data Freshness

| Data Type | Freshness | Storage |
|-----------|-----------|---------|
| **Price** | Daily (always fresh) | Not cached |
| **Fundamentals** (earnings) | Weekly (max 7 days old) | Git repo |
| **Fundamentals** (normal) | Quarterly (max 90 days old) | Git repo |

### Git Repository Impact

**Storage:**
- Fundamental cache: ~19 MB total
- Daily commits: 42-543 files updated
- Git handles this efficiently (small JSON files)

**Commit size:**
- Earnings season: ~3 MB/day (543 files)
- Normal: ~200 KB/day (42 files)

## Advantages of This Approach

✅ **Price Data**: Always fresh (fetched daily)
✅ **Fundamentals**: Persist 90+ days (in Git, not 7-day cache)
✅ **Earnings Aware**: Refreshes weekly during earnings season
✅ **No External Storage**: Uses Git repository (free)
✅ **Works Across Runs**: Every workflow run has access to cache
✅ **Rate Limit Safe**: 74% fewer calls than before
✅ **Version Controlled**: Can track fundamental changes over time

## Disadvantages (Minor)

⚠️ **Git repo size grows**: ~200 KB - 3 MB per day (acceptable)
⚠️ **Daily commits**: Creates commit history (can squash periodically)

## Alternative: Branch-Based Storage

If you don't want commits on main branch:

```yaml
- name: Push changes
  uses: ad-m/github-push-action@v0.8.0
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    branch: fundamental-cache  # Separate branch
```

Then merge periodically or keep separate.

## Sources

- [GitHub Actions Artifacts vs Cache](https://echobind.com/post/difference-between-artifacts-and-cache-in-GitHub-Actions)
- [Storing workflow data as artifacts](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)
- [GitHub Actions Retention Days](https://github.blog/changelog/2020-10-08-github-actions-ability-to-change-retention-days-for-artifacts-and-logs/)
- [Best practices for persistence between workflow runs](https://github.com/orgs/community/discussions/137587)
