"""Financial Modeling Prep (FMP) API fetcher for detailed quarterly fundamentals.

FMP provides comprehensive financial data including:
- Quarterly income statements (net margins, operating margins)
- Balance sheets (inventory details)
- Cash flow statements
- Ratios and metrics

Free tier: 250 requests/day
Get free API key: https://site.financialmodelingprep.com/
"""

import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FMPFetcher:
    """Fetch detailed quarterly fundamentals from Financial Modeling Prep."""

    def __init__(self, api_key: Optional[str] = None, cache_dir: str = "./data/cache"):
        """Initialize FMP fetcher.

        Args:
            api_key: FMP API key (or set FMP_API_KEY env variable)
            cache_dir: Directory for caching responses
        """
        self.api_key = api_key or os.getenv('FMP_API_KEY')

        if not self.api_key:
            logger.warning(
                "No FMP API key found! Set FMP_API_KEY environment variable or pass api_key parameter.\n"
                "Get free key at: https://site.financialmodelingprep.com/developer/docs"
            )

        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.cache_dir = Path(cache_dir) / "fmp"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Bandwidth tracking (30-day limit: 20 GB)
        self.bandwidth_used = 0
        self.bandwidth_limit = 20 * 1024 * 1024 * 1024  # 20 GB in bytes

        logger.info("FMPFetcher initialized")

    def _get_cache_path(self, ticker: str, endpoint: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / f"{ticker}_{endpoint}.pkl"

    def _is_cache_valid(self, cache_path: Path, hours: int = 24) -> bool:
        """Check if cache is valid.

        Uses longer cache (7 days) for non-earnings periods,
        shorter cache (6 hours) during earnings season.
        """
        if not cache_path.exists():
            return False

        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)

        # Adjust cache duration based on earnings season proximity
        if self._is_earnings_season():
            # During earnings season (Jan 15-Feb 15, Apr 15-May 15, Jul 15-Aug 15, Oct 15-Nov 15)
            # Use shorter cache to catch new earnings
            cache_hours = 6
        else:
            # Outside earnings season, use longer cache to save bandwidth
            cache_hours = 168  # 7 days

        return datetime.now() - file_time < timedelta(hours=cache_hours)

    def _is_earnings_season(self) -> bool:
        """Check if currently in earnings season.

        Earnings seasons (roughly):
        - Q4: Jan 15 - Feb 15
        - Q1: Apr 15 - May 15
        - Q2: Jul 15 - Aug 15
        - Q3: Oct 15 - Nov 15
        """
        now = datetime.now()
        month = now.month
        day = now.day

        earnings_windows = [
            (1, 15, 2, 15),  # Q4 earnings: Jan 15 - Feb 15
            (4, 15, 5, 15),  # Q1 earnings: Apr 15 - May 15
            (7, 15, 8, 15),  # Q2 earnings: Jul 15 - Aug 15
            (10, 15, 11, 15) # Q3 earnings: Oct 15 - Nov 15
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

    def _fetch(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Fetch from FMP API with rate limiting.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response or None
        """
        if not self.api_key:
            logger.error("Cannot fetch without API key")
            return None

        try:
            # Add API key to params
            params = params or {}
            params['apikey'] = self.api_key

            url = f"{self.base_url}/{endpoint}"

            # Rate limiting - be respectful
            time.sleep(0.1)  # 10 requests/second max

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            # Track bandwidth usage
            response_size = len(response.content)
            self.bandwidth_used += response_size

            # Check bandwidth limit
            if self.bandwidth_used > self.bandwidth_limit:
                logger.warning(
                    f"FMP bandwidth limit exceeded! "
                    f"Used: {self.bandwidth_used / 1024 / 1024:.1f} MB / "
                    f"{self.bandwidth_limit / 1024 / 1024 / 1024:.1f} GB"
                )

            data = response.json()

            # Check for error in response
            if isinstance(data, dict) and 'Error Message' in data:
                logger.error(f"FMP API error: {data['Error Message']}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from FMP: {e}")
            return None

    def fetch_income_statement(self, ticker: str, quarterly: bool = True, limit: int = 8) -> List[Dict]:
        """Fetch income statement data.

        Args:
            ticker: Stock ticker
            quarterly: True for quarterly, False for annual
            limit: Number of periods to fetch

        Returns:
            List of income statement periods
        """
        cache_key = f"income_{'q' if quarterly else 'a'}"
        cache_path = self._get_cache_path(ticker, cache_key)

        # Check cache
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        # Fetch from API
        period = "quarter" if quarterly else "annual"
        endpoint = f"income-statement/{ticker}"
        params = {'period': period, 'limit': limit}

        data = self._fetch(endpoint, params)

        if data:
            # Cache result
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

        return data or []

    def fetch_balance_sheet(self, ticker: str, quarterly: bool = True, limit: int = 8) -> List[Dict]:
        """Fetch balance sheet data.

        Args:
            ticker: Stock ticker
            quarterly: True for quarterly, False for annual
            limit: Number of periods to fetch

        Returns:
            List of balance sheet periods
        """
        cache_key = f"balance_{'q' if quarterly else 'a'}"
        cache_path = self._get_cache_path(ticker, cache_key)

        # Check cache
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        # Fetch from API
        period = "quarter" if quarterly else "annual"
        endpoint = f"balance-sheet-statement/{ticker}"
        params = {'period': period, 'limit': limit}

        data = self._fetch(endpoint, params)

        if data:
            # Cache result
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

        return data or []

    def fetch_cash_flow(self, ticker: str, quarterly: bool = True, limit: int = 8) -> List[Dict]:
        """Fetch cash flow statement data.

        Args:
            ticker: Stock ticker
            quarterly: True for quarterly, False for annual
            limit: Number of periods to fetch

        Returns:
            List of cash flow periods
        """
        cache_key = f"cashflow_{'q' if quarterly else 'a'}"
        cache_path = self._get_cache_path(ticker, cache_key)

        # Check cache
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        # Fetch from API
        period = "quarter" if quarterly else "annual"
        endpoint = f"cash-flow-statement/{ticker}"
        params = {'period': period, 'limit': limit}

        data = self._fetch(endpoint, params)

        if data:
            # Cache result
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

        return data or []

    def fetch_key_metrics(self, ticker: str, quarterly: bool = True, limit: int = 8) -> List[Dict]:
        """Fetch key financial metrics and ratios.

        Args:
            ticker: Stock ticker
            quarterly: True for quarterly, False for annual
            limit: Number of periods to fetch

        Returns:
            List of metric periods
        """
        cache_key = f"metrics_{'q' if quarterly else 'a'}"
        cache_path = self._get_cache_path(ticker, cache_key)

        # Check cache
        if self._is_cache_valid(cache_path):
            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        # Fetch from API
        period = "quarter" if quarterly else "annual"
        endpoint = f"key-metrics/{ticker}"
        params = {'period': period, 'limit': limit}

        data = self._fetch(endpoint, params)

        if data:
            # Cache result
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

        return data or []

    def fetch_comprehensive_fundamentals(self, ticker: str) -> Dict:
        """Fetch comprehensive quarterly fundamentals.

        Returns:
            Dict with income statements, balance sheets, cash flow, and metrics
        """
        logger.info(f"Fetching comprehensive fundamentals for {ticker}")

        return {
            'ticker': ticker,
            'income_statement': self.fetch_income_statement(ticker, quarterly=True, limit=8),
            'balance_sheet': self.fetch_balance_sheet(ticker, quarterly=True, limit=8),
            'cash_flow': self.fetch_cash_flow(ticker, quarterly=True, limit=8),
            'key_metrics': self.fetch_key_metrics(ticker, quarterly=True, limit=8),
            'fetch_date': datetime.now().isoformat()
        }

    def create_enhanced_snapshot(self, ticker: str, data: Dict = None) -> str:
        """Create enhanced fundamental snapshot with net margins, inventory, etc.

        Args:
            ticker: Stock ticker
            data: Pre-fetched data, or will fetch if None

        Returns:
            Formatted snapshot string
        """
        if data is None:
            data = self.fetch_comprehensive_fundamentals(ticker)

        if not data or not data.get('income_statement'):
            return f"ENHANCED FUNDAMENTAL SNAPSHOT - {ticker}\nNo data available"

        snapshot = [
            "",
            "="*60,
            f"ENHANCED FUNDAMENTAL SNAPSHOT - {ticker}",
            "="*60,
            ""
        ]

        # Latest quarter data
        income = data['income_statement'][0] if data.get('income_statement') else {}
        balance = data['balance_sheet'][0] if data.get('balance_sheet') else {}
        prev_income = data['income_statement'][1] if len(data.get('income_statement', [])) > 1 else {}
        prev_balance = data['balance_sheet'][1] if len(data.get('balance_sheet', [])) > 1 else {}

        # Revenue analysis
        revenue = income.get('revenue', 0)
        prev_revenue = prev_income.get('revenue', 0)

        if revenue and prev_revenue:
            rev_change = ((revenue - prev_revenue) / prev_revenue * 100)
            if rev_change > 20:
                snapshot.append(f"✓ Revenue: ACCELERATING (${revenue/1e9:.2f}B, +{rev_change:.1f}% QoQ)")
            elif rev_change > 5:
                snapshot.append(f"✓ Revenue: Growing (${revenue/1e9:.2f}B, +{rev_change:.1f}% QoQ)")
            elif rev_change > 0:
                snapshot.append(f"• Revenue: Modest growth (${revenue/1e9:.2f}B, +{rev_change:.1f}% QoQ)")
            else:
                snapshot.append(f"✗ Revenue: DECLINING (${revenue/1e9:.2f}B, {rev_change:.1f}% QoQ)")

        # EPS analysis
        eps = income.get('eps', 0)
        prev_eps = prev_income.get('eps', 0)

        if eps and prev_eps:
            eps_change = ((eps - prev_eps) / abs(prev_eps) * 100) if prev_eps != 0 else 0
            if eps_change > 25:
                snapshot.append(f"✓ EPS: STRONG growth (${eps:.2f}, +{eps_change:.1f}% QoQ)")
            elif eps_change > 10:
                snapshot.append(f"✓ EPS: Growing (${eps:.2f}, +{eps_change:.1f}% QoQ)")
            elif eps_change > 0:
                snapshot.append(f"• EPS: Slight growth (${eps:.2f}, +{eps_change:.1f}% QoQ)")
            else:
                snapshot.append(f"✗ EPS: DECLINING (${eps:.2f}, {eps_change:.1f}% QoQ)")

        # Margin analysis - NET MARGINS!
        net_margin = income.get('netIncomeRatio', 0) * 100  # As percentage
        gross_margin = income.get('grossProfitRatio', 0) * 100
        operating_margin = income.get('operatingIncomeRatio', 0) * 100

        prev_net_margin = prev_income.get('netIncomeRatio', 0) * 100
        margin_change = net_margin - prev_net_margin

        snapshot.append("")
        snapshot.append("Margins:")
        snapshot.append(f"  Gross Margin:     {gross_margin:.1f}%")
        snapshot.append(f"  Operating Margin: {operating_margin:.1f}%")

        if margin_change > 1:
            snapshot.append(f"  Net Margin:       {net_margin:.1f}% ✓ EXPANDING (+{margin_change:.1f}pp)")
        elif margin_change > 0:
            snapshot.append(f"  Net Margin:       {net_margin:.1f}% • Stable (+{margin_change:.1f}pp)")
        elif margin_change > -1:
            snapshot.append(f"  Net Margin:       {net_margin:.1f}% • Flat ({margin_change:.1f}pp)")
        else:
            snapshot.append(f"  Net Margin:       {net_margin:.1f}% ✗ CONTRACTING ({margin_change:.1f}pp)")

        # Inventory analysis
        inventory = balance.get('inventory', 0)
        prev_inventory = prev_balance.get('inventory', 0)

        if inventory and prev_inventory:
            inv_change = ((inventory - prev_inventory) / prev_inventory * 100)
            inv_to_revenue = (inventory / revenue * 100) if revenue else 0

            snapshot.append("")
            snapshot.append("Inventory:")
            snapshot.append(f"  Total: ${inventory/1e9:.2f}B ({inv_to_revenue:.1f}% of revenue)")

            if inv_change > 15:
                snapshot.append(f"  ⚠ BUILDING rapidly (+{inv_change:.1f}% QoQ)")
                snapshot.append("  → Potential demand weakness")
            elif inv_change > 5:
                snapshot.append(f"  • Moderate build (+{inv_change:.1f}% QoQ)")
            elif inv_change > 0:
                snapshot.append(f"  • Slight increase (+{inv_change:.1f}% QoQ)")
            else:
                snapshot.append(f"  ✓ Drawing down ({inv_change:.1f}% QoQ)")
                snapshot.append("  → Strong demand signal")

        # Overall assessment
        snapshot.append("")
        snapshot.append("Overall Assessment:")

        concerns = []
        if revenue and prev_revenue and ((revenue - prev_revenue) / prev_revenue) < 0:
            concerns.append('revenue declining')
        if eps and prev_eps and ((eps - prev_eps) / abs(prev_eps)) < 0:
            concerns.append('EPS declining')
        if margin_change < -2:
            concerns.append('margins contracting')
        if inventory and prev_inventory and ((inventory - prev_inventory) / prev_inventory) > 15:
            concerns.append('inventory building')

        if len(concerns) == 0:
            snapshot.append("✓ Fundamentals SUPPORT technical breakout")
        else:
            snapshot.append(f"⚠ Concerns: {', '.join(concerns)}")
            if len(concerns) >= 2:
                snapshot.append("✗ Fundamentals CONTRADICT technical breakout")

        snapshot.append("="*60)

        return "\n".join(snapshot)

    def get_bandwidth_stats(self) -> Dict[str, any]:
        """Get bandwidth usage statistics.

        Returns:
            Dict with bandwidth usage info
        """
        used_mb = self.bandwidth_used / 1024 / 1024
        limit_gb = self.bandwidth_limit / 1024 / 1024 / 1024
        pct_used = (self.bandwidth_used / self.bandwidth_limit * 100) if self.bandwidth_limit > 0 else 0

        return {
            'bandwidth_used_mb': round(used_mb, 2),
            'bandwidth_limit_gb': round(limit_gb, 2),
            'bandwidth_pct_used': round(pct_used, 2),
            'is_earnings_season': self._is_earnings_season(),
            'cache_hours': 6 if self._is_earnings_season() else 168
        }
