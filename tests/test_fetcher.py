"""Comprehensive test suite for YahooFinanceFetcher.

This module tests all functionality of the data fetching module including
API calls, caching, error handling, and retry logic.
"""

import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import pytest
import yfinance as yf

from src.data.fetcher import YahooFinanceFetcher


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory for testing.

    Args:
        tmp_path: pytest fixture for temporary directories.

    Returns:
        Path to temporary cache directory.
    """
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def fetcher(temp_cache_dir):
    """Create a YahooFinanceFetcher instance with temporary cache.

    Args:
        temp_cache_dir: Temporary cache directory fixture.

    Returns:
        YahooFinanceFetcher instance configured for testing.
    """
    return YahooFinanceFetcher(
        cache_dir=temp_cache_dir,
        cache_expiry_hours=24,
        max_retries=3,
        retry_delay=1
    )


@pytest.fixture
def mock_stock_info():
    """Mock stock info data returned by yfinance.

    Returns:
        Dictionary simulating yfinance Ticker.info response.
    """
    return {
        'symbol': 'AAPL',
        'longName': 'Apple Inc.',
        'sector': 'Technology',
        'currentPrice': 175.50,
        'regularMarketPrice': 175.50,
        'fiftyTwoWeekHigh': 199.62,
        'fiftyTwoWeekLow': 164.08,
        'trailingPE': 28.5,
        'forwardPE': 26.2,
        'priceToBook': 45.3,
        'debtToEquity': 173.0,
        'freeCashflow': 99000000000,
        'marketCap': 2750000000000,
        'trailingEps': 6.16,
        'forwardEps': 6.70,
        'dividendYield': 0.0051
    }


@pytest.fixture
def mock_price_history():
    """Mock price history data returned by yfinance.

    Returns:
        DataFrame simulating yfinance Ticker.history() response.
    """
    dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='D')
    data = {
        'Open': [150.0 + i * 0.1 for i in range(len(dates))],
        'High': [152.0 + i * 0.1 for i in range(len(dates))],
        'Low': [149.0 + i * 0.1 for i in range(len(dates))],
        'Close': [151.0 + i * 0.1 for i in range(len(dates))],
        'Volume': [1000000 + i * 1000 for i in range(len(dates))]
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'Date'
    return df


class TestYahooFinanceFetcherInit:
    """Test suite for YahooFinanceFetcher initialization."""

    def test_init_creates_cache_directory(self, temp_cache_dir):
        """Test that initializer creates cache directory if it doesn't exist."""
        cache_path = Path(temp_cache_dir) / "new_dir"
        fetcher = YahooFinanceFetcher(cache_dir=str(cache_path))

        assert cache_path.exists()
        assert cache_path.is_dir()

    def test_init_with_default_parameters(self, temp_cache_dir):
        """Test initialization with default parameters."""
        fetcher = YahooFinanceFetcher(cache_dir=temp_cache_dir)

        assert fetcher.cache_dir == Path(temp_cache_dir)
        assert fetcher.cache_expiry_hours == 24
        assert fetcher.max_retries == 3
        assert fetcher.retry_delay == 2

    def test_init_with_custom_parameters(self, temp_cache_dir):
        """Test initialization with custom parameters."""
        fetcher = YahooFinanceFetcher(
            cache_dir=temp_cache_dir,
            cache_expiry_hours=12,
            max_retries=5,
            retry_delay=3
        )

        assert fetcher.cache_expiry_hours == 12
        assert fetcher.max_retries == 5
        assert fetcher.retry_delay == 3


class TestFetchFundamentals:
    """Test suite for fetch_fundamentals method."""

    def test_fetch_fundamentals_success(self, fetcher, mock_stock_info):
        """Test successful fetching of fundamental data."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            result = fetcher.fetch_fundamentals("AAPL")

            assert result['ticker'] == 'AAPL'
            assert result['name'] == 'Apple Inc.'
            assert result['sector'] == 'Technology'
            assert result['current_price'] == 175.50
            assert result['pe_ratio'] == 28.5
            assert result['pb_ratio'] == 45.3
            assert result['debt_to_equity'] == 173.0
            assert result['free_cash_flow'] == 99000000000
            assert 'fetch_date' in result

    def test_fetch_fundamentals_with_missing_data(self, fetcher):
        """Test fetching fundamentals with incomplete data."""
        incomplete_info = {
            'symbol': 'TEST',
            'longName': 'Test Company',
            'sector': 'Technology',
            'currentPrice': 100.0,
            # Missing P/E, P/B, etc.
        }

        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = incomplete_info
            mock_ticker.return_value = mock_instance

            result = fetcher.fetch_fundamentals("TEST")

            assert result['ticker'] == 'TEST'
            assert result['current_price'] == 100.0
            assert result['pe_ratio'] is None
            assert result['pb_ratio'] is None

    def test_fetch_fundamentals_uses_cache(self, fetcher, mock_stock_info):
        """Test that fundamentals are cached and reused."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            # First fetch - should hit API
            result1 = fetcher.fetch_fundamentals("AAPL")

            # Second fetch - should use cache
            result2 = fetcher.fetch_fundamentals("AAPL")

            # Should only call API once
            assert mock_ticker.call_count == 1
            assert result1 == result2

    def test_fetch_fundamentals_cache_expiry(self, temp_cache_dir, mock_stock_info):
        """Test that expired cache is refreshed."""
        fetcher = YahooFinanceFetcher(
            cache_dir=temp_cache_dir,
            cache_expiry_hours=0  # Immediate expiry
        )

        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            # First fetch
            fetcher.fetch_fundamentals("AAPL")

            # Modify cache file timestamp to be old
            cache_path = fetcher._get_cache_path("AAPL", 'fundamentals')
            old_time = time.time() - 3600  # 1 hour ago
            os.utime(cache_path, (old_time, old_time))

            # Second fetch - should re-fetch due to expiry
            fetcher.fetch_fundamentals("AAPL")

            # Should call API twice
            assert mock_ticker.call_count == 2

    def test_fetch_fundamentals_network_error_with_retry(self, fetcher):
        """Test retry logic on network failures."""
        with patch('yfinance.Ticker') as mock_ticker:
            # First two calls fail, third succeeds
            mock_ticker.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                Mock(info={'symbol': 'AAPL', 'longName': 'Apple Inc.', 'sector': 'Technology'})
            ]

            result = fetcher.fetch_fundamentals("AAPL")

            # Should retry and eventually succeed
            assert mock_ticker.call_count == 3
            assert result['ticker'] == 'AAPL'

    def test_fetch_fundamentals_complete_failure(self, fetcher):
        """Test behavior when all retry attempts fail."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker.side_effect = Exception("Persistent network error")

            result = fetcher.fetch_fundamentals("AAPL")

            # Should return empty dict after max retries
            assert result == {}
            assert mock_ticker.call_count == 3


class TestFetchPriceHistory:
    """Test suite for fetch_price_history method."""

    def test_fetch_price_history_success(self, fetcher, mock_price_history):
        """Test successful fetching of price history."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = {'symbol': 'AAPL'}
            mock_instance.history.return_value = mock_price_history
            mock_ticker.return_value = mock_instance

            result = fetcher.fetch_price_history("AAPL", period="5y")

            assert not result.empty
            assert len(result) == len(mock_price_history)
            assert 'Date' in result.columns
            assert 'Open' in result.columns
            assert 'High' in result.columns
            assert 'Low' in result.columns
            assert 'Close' in result.columns
            assert 'Volume' in result.columns

    def test_fetch_price_history_different_periods(self, fetcher, mock_price_history):
        """Test fetching price history with different time periods."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = {'symbol': 'AAPL'}
            mock_instance.history.return_value = mock_price_history
            mock_ticker.return_value = mock_instance

            # Test different periods
            periods = ["1y", "2y", "5y", "max"]
            for period in periods:
                result = fetcher.fetch_price_history("AAPL", period=period)
                assert not result.empty
                mock_instance.history.assert_called_with(period=period, interval="1d")

    def test_fetch_price_history_uses_cache(self, fetcher, mock_price_history):
        """Test that price history is cached."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = {'symbol': 'AAPL'}
            mock_instance.history.return_value = mock_price_history
            mock_ticker.return_value = mock_instance

            # First fetch
            result1 = fetcher.fetch_price_history("AAPL", period="5y")

            # Second fetch - should use cache
            result2 = fetcher.fetch_price_history("AAPL", period="5y")

            # Should only call API once
            assert mock_ticker.call_count == 1
            pd.testing.assert_frame_equal(result1, result2)

    def test_fetch_price_history_empty_data(self, fetcher):
        """Test handling of empty price history."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = {'symbol': 'INVALID'}
            mock_instance.history.return_value = pd.DataFrame()
            mock_ticker.return_value = mock_instance

            result = fetcher.fetch_price_history("INVALID")

            assert result.empty

    def test_fetch_price_history_network_error(self, fetcher):
        """Test handling of network errors during price fetch."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker.side_effect = Exception("Network error")

            result = fetcher.fetch_price_history("AAPL")

            assert result.empty


class TestFetchMultiple:
    """Test suite for fetch_multiple method."""

    def test_fetch_multiple_success(self, fetcher, mock_stock_info, mock_price_history):
        """Test fetching data for multiple stocks."""
        tickers = ["AAPL", "MSFT", "GOOGL"]

        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_instance.history.return_value = mock_price_history
            mock_ticker.return_value = mock_instance

            fundamentals_df, prices_df = fetcher.fetch_multiple(tickers)

            # Check fundamentals
            assert len(fundamentals_df) == len(tickers)
            assert 'ticker' in fundamentals_df.columns

            # Check prices
            assert not prices_df.empty
            assert 'ticker' in prices_df.columns
            assert set(prices_df['ticker'].unique()) == set(tickers)

    def test_fetch_multiple_partial_failure(self, fetcher, mock_stock_info, mock_price_history):
        """Test fetch_multiple when some tickers fail."""
        tickers = ["AAPL", "INVALID", "GOOGL"]

        with patch('yfinance.Ticker') as mock_ticker:
            def side_effect(ticker):
                if ticker == "INVALID":
                    raise Exception("Invalid ticker")
                mock_instance = Mock()
                mock_instance.info = mock_stock_info
                mock_instance.history.return_value = mock_price_history
                return mock_instance

            mock_ticker.side_effect = side_effect

            fundamentals_df, prices_df = fetcher.fetch_multiple(tickers)

            # Should have data for valid tickers only
            assert len(fundamentals_df) == 2  # AAPL and GOOGL
            assert 'INVALID' not in fundamentals_df['ticker'].values

    def test_fetch_multiple_empty_list(self, fetcher):
        """Test fetch_multiple with empty ticker list."""
        fundamentals_df, prices_df = fetcher.fetch_multiple([])

        assert fundamentals_df.empty
        assert prices_df.empty

    def test_fetch_multiple_custom_period(self, fetcher, mock_stock_info, mock_price_history):
        """Test fetch_multiple with custom period."""
        tickers = ["AAPL", "MSFT"]

        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_instance.history.return_value = mock_price_history
            mock_ticker.return_value = mock_instance

            fundamentals_df, prices_df = fetcher.fetch_multiple(tickers, period="1y")

            assert not prices_df.empty
            # Verify history was called with correct period
            mock_instance.history.assert_called_with(period="1y", interval="1d")


class TestCacheManagement:
    """Test suite for cache management methods."""

    def test_clear_cache_specific_ticker(self, fetcher, mock_stock_info):
        """Test clearing cache for a specific ticker."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            # Fetch data to create cache
            fetcher.fetch_fundamentals("AAPL")
            fetcher.fetch_fundamentals("MSFT")

            # Clear AAPL cache only
            fetcher.clear_cache("AAPL")

            # AAPL cache should be gone, MSFT should remain
            aapl_cache = fetcher._get_cache_path("AAPL", 'fundamentals')
            msft_cache = fetcher._get_cache_path("MSFT", 'fundamentals')

            assert not aapl_cache.exists()
            assert msft_cache.exists()

    def test_clear_cache_all(self, fetcher, mock_stock_info):
        """Test clearing all cache."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            # Fetch data for multiple tickers
            fetcher.fetch_fundamentals("AAPL")
            fetcher.fetch_fundamentals("MSFT")
            fetcher.fetch_fundamentals("GOOGL")

            # Clear all cache
            fetcher.clear_cache()

            # All cache should be cleared
            cache_files = list(fetcher.cache_dir.glob("*.pkl"))
            assert len(cache_files) == 0

    def test_clear_cache_nonexistent_ticker(self, fetcher):
        """Test clearing cache for non-existent ticker."""
        # Should not raise an exception
        fetcher.clear_cache("NONEXISTENT")

    def test_is_cache_valid(self, fetcher, temp_cache_dir):
        """Test cache validation logic."""
        cache_path = Path(temp_cache_dir) / "test_cache.pkl"

        # Non-existent cache should be invalid
        assert not fetcher._is_cache_valid(cache_path)

        # Create a fresh cache file
        with open(cache_path, 'wb') as f:
            pickle.dump({'test': 'data'}, f)

        # Fresh cache should be valid
        assert fetcher._is_cache_valid(cache_path)

        # Make cache old
        old_time = time.time() - (fetcher.cache_expiry_hours + 1) * 3600
        os.utime(cache_path, (old_time, old_time))

        # Old cache should be invalid
        assert not fetcher._is_cache_valid(cache_path)


class TestErrorHandling:
    """Test suite for error handling scenarios."""

    def test_fetch_with_corrupted_cache(self, fetcher, mock_stock_info, temp_cache_dir):
        """Test handling of corrupted cache files."""
        # Create corrupted cache file
        cache_path = fetcher._get_cache_path("AAPL", 'fundamentals')
        with open(cache_path, 'wb') as f:
            f.write(b'corrupted data')

        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            # Should handle corrupted cache and fetch fresh data
            result = fetcher.fetch_fundamentals("AAPL")

            assert result['ticker'] == 'AAPL'
            assert mock_ticker.call_count == 1

    def test_fetch_with_permission_error(self, fetcher, mock_stock_info):
        """Test handling of cache write permission errors."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_instance = Mock()
            mock_instance.info = mock_stock_info
            mock_ticker.return_value = mock_instance

            with patch('builtins.open', side_effect=PermissionError):
                # Should still return data even if cache write fails
                result = fetcher.fetch_fundamentals("AAPL")
                assert result['ticker'] == 'AAPL'

    def test_fetch_fundamentals_exception_handling(self, fetcher):
        """Test that exceptions are properly caught and logged."""
        with patch('yfinance.Ticker') as mock_ticker:
            mock_ticker.side_effect = Exception("Unexpected error")

            # Should return empty dict, not raise exception
            result = fetcher.fetch_fundamentals("AAPL")
            assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
