"""Data fetching module for retrieving stock data from Yahoo Finance.

This module provides a robust interface for fetching stock fundamentals and
price history with caching, error handling, and retry logic.
"""

import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YahooFinanceFetcher:
    """Fetches stock data from Yahoo Finance with caching and error handling.

    This class provides methods to fetch fundamental data and price history
    for stocks, with automatic caching to reduce API calls and retry logic
    for network failures.

    Attributes:
        cache_dir: Directory path for storing cached data files.
        cache_expiry_hours: Number of hours before cache expires (default: 24).
        max_retries: Maximum number of retry attempts for API calls (default: 3).
        retry_delay: Delay in seconds between retry attempts (default: 2).

    Example:
        >>> fetcher = YahooFinanceFetcher()
        >>> fundamentals = fetcher.fetch_fundamentals("AAPL")
        >>> prices = fetcher.fetch_price_history("AAPL", period="5y")
        >>> all_data = fetcher.fetch_multiple(["AAPL", "MSFT", "GOOGL"])
    """

    def __init__(
        self,
        cache_dir: str = "./data/cache",
        cache_expiry_hours: int = 24,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> None:
        """Initialize the YahooFinanceFetcher.

        Args:
            cache_dir: Directory path for caching data. Created if it doesn't exist.
            cache_expiry_hours: Hours before cached data expires.
            max_retries: Maximum retry attempts for failed API calls.
            retry_delay: Seconds to wait between retries.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_expiry_hours = cache_expiry_hours
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        logger.info(f"YahooFinanceFetcher initialized with cache_dir: {cache_dir}")

    def _get_cache_path(self, ticker: str, data_type: str) -> Path:
        """Get the cache file path for a given ticker and data type.

        Args:
            ticker: Stock ticker symbol.
            data_type: Type of data ('fundamentals' or 'prices').

        Returns:
            Path object for the cache file.
        """
        return self.cache_dir / f"{ticker}_{data_type}.pkl"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached data is still valid.

        Args:
            cache_path: Path to the cache file.

        Returns:
            True if cache exists and hasn't expired, False otherwise.
        """
        if not cache_path.exists():
            return False

        file_modified = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = datetime.now() - timedelta(hours=self.cache_expiry_hours)

        is_valid = file_modified > expiry_time
        if is_valid:
            logger.debug(f"Cache valid for {cache_path.name}")
        else:
            logger.debug(f"Cache expired for {cache_path.name}")

        return is_valid

    def _load_from_cache(self, cache_path: Path) -> Optional[any]:
        """Load data from cache file.

        Args:
            cache_path: Path to the cache file.

        Returns:
            Cached data if successful, None otherwise.
        """
        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            logger.info(f"Loaded data from cache: {cache_path.name}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_path.name}: {e}")
            return None

    def _save_to_cache(self, data: any, cache_path: Path) -> None:
        """Save data to cache file.

        Args:
            data: Data to cache.
            cache_path: Path to save the cache file.
        """
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Saved data to cache: {cache_path.name}")
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_path.name}: {e}")

    def _fetch_with_retry(self, ticker: str) -> Optional[yf.Ticker]:
        """Fetch ticker data with retry logic.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            yfinance Ticker object if successful, None otherwise.
        """
        for attempt in range(self.max_retries):
            try:
                stock = yf.Ticker(ticker)
                # Test if ticker is valid by accessing info
                _ = stock.info
                return stock
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {ticker}: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to fetch {ticker} after {self.max_retries} attempts")
                    return None

    def fetch_fundamentals(self, ticker: str) -> Dict[str, any]:
        """Fetch fundamental data for a stock.

        Retrieves key fundamental metrics including current price, 52-week high/low,
        P/E ratio, P/B ratio, debt-to-equity, and free cash flow.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').

        Returns:
            Dictionary containing fundamental metrics. Returns empty dict on failure.

        Example:
            >>> fetcher = YahooFinanceFetcher()
            >>> data = fetcher.fetch_fundamentals("AAPL")
            >>> print(data['pe_ratio'])
        """
        cache_path = self._get_cache_path(ticker, 'fundamentals')

        # Check cache first
        if self._is_cache_valid(cache_path):
            cached_data = self._load_from_cache(cache_path)
            if cached_data is not None:
                return cached_data

        # Fetch from API
        logger.info(f"Fetching fundamentals for {ticker}")
        stock = self._fetch_with_retry(ticker)

        if stock is None:
            logger.error(f"Could not fetch fundamentals for {ticker}")
            return {}

        try:
            info = stock.info

            # Extract fundamental metrics with safe defaults
            fundamentals = {
                'ticker': ticker,
                'name': info.get('longName', ticker),
                'sector': info.get('sector', 'Unknown'),
                'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'week_52_high': info.get('fiftyTwoWeekHigh'),
                'week_52_low': info.get('fiftyTwoWeekLow'),
                'pe_ratio': info.get('trailingPE') or info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
                'debt_to_equity': info.get('debtToEquity'),
                'free_cash_flow': info.get('freeCashflow'),
                'market_cap': info.get('marketCap'),
                'trailing_eps': info.get('trailingEps'),
                'forward_eps': info.get('forwardEps'),
                'dividend_yield': info.get('dividendYield'),
                'fetch_date': datetime.now().isoformat()
            }

            # Log warnings for missing data
            missing_fields = [k for k, v in fundamentals.items() if v is None and k not in ['ticker', 'name', 'sector', 'fetch_date']]
            if missing_fields:
                logger.warning(f"Missing data for {ticker}: {', '.join(missing_fields)}")

            # Cache the results
            self._save_to_cache(fundamentals, cache_path)

            logger.info(f"Successfully fetched fundamentals for {ticker}")
            return fundamentals

        except Exception as e:
            logger.error(f"Error extracting fundamentals for {ticker}: {e}")
            return {}

    def fetch_price_history(
        self,
        ticker: str,
        period: str = "5y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical price data for a stock.

        Retrieves OHLCV (Open, High, Low, Close, Volume) data for the specified period.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL').
            period: Time period for historical data. Valid values: 1d, 5d, 1mo, 3mo,
                   6mo, 1y, 2y, 5y, 10y, ytd, max. Default is '5y'.
            interval: Data interval. Valid values: 1m, 2m, 5m, 15m, 30m, 60m, 90m,
                     1h, 1d, 5d, 1wk, 1mo, 3mo. Default is '1d'.

        Returns:
            DataFrame with columns: Date (index), Open, High, Low, Close, Volume.
            Returns empty DataFrame on failure.

        Example:
            >>> fetcher = YahooFinanceFetcher()
            >>> prices = fetcher.fetch_price_history("AAPL", period="1y")
            >>> print(prices.head())
        """
        cache_path = self._get_cache_path(ticker, f'prices_{period}_{interval}')

        # Check cache first
        if self._is_cache_valid(cache_path):
            cached_data = self._load_from_cache(cache_path)
            if cached_data is not None and isinstance(cached_data, pd.DataFrame):
                return cached_data

        # Fetch from API
        logger.info(f"Fetching price history for {ticker} (period={period}, interval={interval})")
        stock = self._fetch_with_retry(ticker)

        if stock is None:
            logger.error(f"Could not fetch price history for {ticker}")
            return pd.DataFrame()

        try:
            # Fetch historical data
            hist = stock.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"No price history data available for {ticker}")
                return pd.DataFrame()

            # Clean up the DataFrame - keep DatetimeIndex for consistency with git_fetcher
            # DO NOT reset_index() - we want to preserve the DatetimeIndex from yfinance
            hist.columns = [col.capitalize() for col in hist.columns]

            # Ensure index is DatetimeIndex (yfinance should provide this)
            if not isinstance(hist.index, pd.DatetimeIndex):
                logger.warning(f"{ticker}: yfinance returned non-DatetimeIndex: {type(hist.index)}")
                return pd.DataFrame()

            # Select only OHLCV columns (no 'Date' column - it's the index)
            available_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            hist = hist[[col for col in available_cols if col in hist.columns]]

            # Cache the results
            self._save_to_cache(hist, cache_path)

            logger.info(f"Successfully fetched {len(hist)} price records for {ticker}")
            return hist

        except Exception as e:
            logger.error(f"Error fetching price history for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_multiple(
        self,
        tickers: List[str],
        period: str = "5y"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch fundamentals and price history for multiple stocks.

        Args:
            tickers: List of stock ticker symbols.
            period: Time period for historical data (default: '5y').

        Returns:
            Tuple of (fundamentals_df, prices_df):
                - fundamentals_df: DataFrame with one row per ticker
                - prices_df: DataFrame with all price data, includes 'ticker' column

        Example:
            >>> fetcher = YahooFinanceFetcher()
            >>> fundamentals, prices = fetcher.fetch_multiple(["AAPL", "MSFT", "GOOGL"])
            >>> print(fundamentals[['ticker', 'pe_ratio', 'pb_ratio']])
        """
        logger.info(f"Fetching data for {len(tickers)} tickers")

        all_fundamentals = []
        all_prices = []

        for ticker in tickers:
            # Fetch fundamentals
            fundamentals = self.fetch_fundamentals(ticker)
            if fundamentals:
                all_fundamentals.append(fundamentals)

            # Fetch price history
            prices = self.fetch_price_history(ticker, period=period)
            if not prices.empty:
                prices['ticker'] = ticker
                all_prices.append(prices)

        # Combine all data
        fundamentals_df = pd.DataFrame(all_fundamentals) if all_fundamentals else pd.DataFrame()
        prices_df = pd.concat(all_prices, ignore_index=True) if all_prices else pd.DataFrame()

        logger.info(
            f"Fetched {len(all_fundamentals)}/{len(tickers)} fundamentals, "
            f"{len(all_prices)}/{len(tickers)} price histories"
        )

        return fundamentals_df, prices_df

    def clear_cache(self, ticker: Optional[str] = None) -> None:
        """Clear cached data.

        Args:
            ticker: If provided, clears cache only for this ticker.
                   If None, clears all cached data.

        Example:
            >>> fetcher = YahooFinanceFetcher()
            >>> fetcher.clear_cache("AAPL")  # Clear only AAPL cache
            >>> fetcher.clear_cache()  # Clear all cache
        """
        if ticker:
            # Clear cache for specific ticker
            pattern = f"{ticker}_*.pkl"
            removed = 0
            for cache_file in self.cache_dir.glob(pattern):
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")
            logger.info(f"Cleared {removed} cache file(s) for {ticker}")
        else:
            # Clear all cache
            removed = 0
            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    cache_file.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")
            logger.info(f"Cleared {removed} cache file(s)")
