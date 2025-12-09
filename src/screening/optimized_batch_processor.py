"""Optimized batch processor with parallel processing and adaptive rate limiting.

This module implements advanced techniques to maximize throughput while avoiding rate limits:
- Parallel batch processing with thread pools
- Adaptive rate limiting based on error rates
- Session reuse and connection pooling
- Bulk data fetching where possible
"""

import logging
import pickle
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from src.data.fetcher import YahooFinanceFetcher
from src.data.fundamentals_fetcher import fetch_quarterly_financials, analyze_fundamentals_for_signal
from src.data.git_storage_fetcher import GitStorageFetcher
from ..screening.phase_indicators import classify_phase, calculate_relative_strength

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OptimizedBatchProcessor:
    """Optimized batch processor with parallel processing and smart rate limiting."""

    def __init__(
        self,
        cache_dir: str = "./data/cache",
        results_dir: str = "./data/batch_results",
        max_workers: int = 3,  # Conservative: 3 workers
        rate_limit_delay: float = 0.5,  # 0.5 sec = 2 TPS per worker
        batch_size: int = 100,
        use_git_storage: bool = False  # Use Git-based fundamental storage
    ):
        """Initialize optimized processor.

        Args:
            cache_dir: Cache directory
            results_dir: Results directory
            max_workers: Number of parallel workers (3 = ~6 TPS effective)
            rate_limit_delay: Delay per worker (0.5 = 2 TPS)
            batch_size: Save progress frequency
            use_git_storage: Use Git-based storage for fundamentals (recommended)
        """
        self.fetcher = YahooFinanceFetcher(cache_dir=cache_dir)
        self.git_fetcher = GitStorageFetcher() if use_git_storage else None
        self.use_git_storage = use_git_storage
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.rate_limit_delay = rate_limit_delay
        self.batch_size = batch_size

        # Effective TPS = max_workers / rate_limit_delay
        effective_tps = max_workers / rate_limit_delay

        self.spy_data = None
        self.spy_price = None
        self.progress_file = self.results_dir / "batch_progress.pkl"
        self.processed_tickers = set()
        self.current_results = []

        # Rate limit tracking and adaptive backoff
        self.request_times = []
        self.error_count = 0
        self.filtered_count = 0  # Stocks that didn't pass filters (not errors)
        self.total_requests = 0
        self.consecutive_errors = 0
        self.backoff_delay = 0.0  # Additional delay when errors detected
        self.last_error_time = None

        # Thread-safe rate limiting
        self.rate_limit_lock = threading.Lock()
        self.last_request_time = 0.0

        # Error tracking by type
        self.error_types = {}  # {error_type: count}
        self.error_examples = {}  # {error_type: example_ticker}

        # Filter tracking
        self.filter_reasons = {}  # {reason: count}

        logger.info(f"OptimizedBatchProcessor initialized")
        logger.info(f"Workers: {max_workers}, Delay: {rate_limit_delay}s")
        logger.info(f"Effective rate: ~{effective_tps:.1f} TPS")

    def load_progress(self) -> Optional[Dict]:
        """Load progress from previous run."""
        if not self.progress_file.exists():
            return None

        try:
            with open(self.progress_file, 'rb') as f:
                progress = pickle.load(f)
            logger.info(f"Loaded progress: {len(progress['processed'])} stocks done")
            return progress
        except Exception as e:
            logger.error(f"Error loading progress: {e}")
            return None

    def save_progress(self, tickers_list: List[str], results: List[Dict]):
        """Save current progress."""
        try:
            progress = {
                'timestamp': datetime.now().isoformat(),
                'total_tickers': len(tickers_list),
                'processed': list(self.processed_tickers),
                'results': results,
                'batch_size': self.batch_size,
                'error_rate': self.error_count / max(self.total_requests, 1)
            }

            with open(self.progress_file, 'wb') as f:
                pickle.dump(progress, f)

        except Exception as e:
            logger.error(f"Error saving progress: {e}")

    def _wait_for_rate_limit(self):
        """Thread-safe rate limiting - ensures minimum delay between ANY requests.

        This method uses a lock to ensure that even with multiple threads,
        only one request can proceed at a time, and each request waits
        the full rate_limit_delay since the last request.
        """
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time

            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                time.sleep(sleep_time)

            # Add adaptive backoff if errors detected
            if self.backoff_delay > 0:
                time.sleep(self.backoff_delay)
                logger.debug(f"Adaptive backoff: +{self.backoff_delay:.1f}s")

            self.last_request_time = time.time()

    def fetch_spy_data(self) -> bool:
        """Fetch SPY benchmark data."""
        try:
            logger.info("Fetching SPY data...")
            # Use 1 year for price data (not 2 years - 50% less data)
            # Use same fetcher as stocks for consistency
            if self.use_git_storage and self.git_fetcher:
                spy_hist = self.git_fetcher.fetch_price_fresh('SPY')
            else:
                spy_hist = self.fetcher.fetch_price_history('SPY', period='1y')

            if spy_hist.empty:
                logger.error("Failed to fetch SPY data")
                return False

            # Ensure DatetimeIndex (yfinance should return this, but verify)
            if not isinstance(spy_hist.index, pd.DatetimeIndex):
                logger.error(f"SPY has invalid index type: {type(spy_hist.index)}")
                logger.error(f"SPY index: {spy_hist.index}")
                return False

            self.spy_data = spy_hist
            self.spy_price = spy_hist['Close'].iloc[-1]
            logger.info(f"SPY ready: {len(spy_hist)} days, ${self.spy_price:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error fetching SPY: {e}")
            return False

    def analyze_single_stock(
        self,
        ticker: str,
        min_price: float,
        max_price: float,
        min_volume: int
    ) -> Optional[Dict]:
        """Analyze one stock with adaptive rate limiting.

        Args:
            ticker: Stock ticker
            min_price: Min price filter
            max_price: Max price filter
            min_volume: Min volume filter

        Returns:
            Analysis dict or None
        """
        try:
            # Thread-safe rate limiting (locks ensure only 1 request at a time)
            self._wait_for_rate_limit()

            self.total_requests += 1

            # Fetch price history (1 year = 250 days, sufficient for 200 SMA)
            if self.use_git_storage and self.git_fetcher:
                price_data = self.git_fetcher.fetch_price_fresh(ticker)
            else:
                price_data = self.fetcher.fetch_price_history(ticker, period='1y')

            if price_data.empty or len(price_data) < 200:
                self.filtered_count += 1
                self.filter_reasons['insufficient_data'] = self.filter_reasons.get('insufficient_data', 0) + 1
                return None

            current_price = price_data['Close'].iloc[-1]

            # Price filter
            if current_price < min_price or current_price > max_price:
                self.filtered_count += 1
                self.filter_reasons['price_range'] = self.filter_reasons.get('price_range', 0) + 1
                return None

            # Volume filter
            if 'Volume' in price_data.columns:
                avg_volume = price_data['Volume'].iloc[-20:].mean()
                if avg_volume < min_volume:
                    self.filtered_count += 1
                    self.filter_reasons['low_volume'] = self.filter_reasons.get('low_volume', 0) + 1
                    return None
            else:
                avg_volume = 0

            # Phase classification
            phase_info = classify_phase(price_data, current_price)
            phase = phase_info['phase']

            if phase not in [1, 2, 3, 4]:
                self.filtered_count += 1
                self.filter_reasons['invalid_phase'] = self.filter_reasons.get('invalid_phase', 0) + 1
                return None

            # RS calculation
            rs_series = calculate_relative_strength(
                price_data['Close'],
                self.spy_data['Close'],
                period=63
            )

            # Fundamentals (only for Phase 1/2)
            quarterly_data = {}
            fundamental_analysis = {}

            if phase in [1, 2]:
                # Use Git-based storage if enabled
                if self.use_git_storage and self.git_fetcher:
                    quarterly_data = self.git_fetcher.fetch_fundamentals_smart(ticker)
                else:
                    quarterly_data = fetch_quarterly_financials(ticker)
                fundamental_analysis = analyze_fundamentals_for_signal(quarterly_data)

            return {
                'ticker': ticker,
                'price_data': price_data,
                'current_price': current_price,
                'avg_volume': avg_volume,
                'phase_info': phase_info,
                'rs_series': rs_series,
                'quarterly_data': quarterly_data,
                'fundamental_analysis': fundamental_analysis
            }

        except Exception as e:
            self.error_count += 1
            self.consecutive_errors += 1
            self.last_error_time = time.time()

            # Track error type
            error_type = type(e).__name__
            error_msg = str(e)

            if error_type not in self.error_types:
                self.error_types[error_type] = 0
                self.error_examples[error_type] = (ticker, error_msg)

            self.error_types[error_type] += 1

            # Log first 5 occurrences of each error type for debugging
            if self.error_types[error_type] <= 5:
                logger.error(f"[ERROR #{self.error_types[error_type]}] {error_type} on {ticker}: {error_msg}")
            elif self.error_types[error_type] == 6:
                logger.info(f"  ({error_type} will now be suppressed, {self.error_types[error_type]} total so far)")

            # Check if it's a rate limit error
            if '429' in error_msg.lower() or 'rate limit' in error_msg.lower() or 'too many requests' in error_msg.lower():
                logger.warning(f"Rate limit hit on {ticker}: {e}")

                # Adaptive backoff - increase delay
                self.backoff_delay = min(self.backoff_delay + 0.5, 5.0)  # Max 5 sec extra
                logger.warning(f"Increasing backoff delay to +{self.backoff_delay:.1f}s")

                # If we hit multiple rate limits, sleep longer immediately
                if self.consecutive_errors >= 3:
                    sleep_time = 30
                    logger.warning(f"Multiple rate limits detected! Sleeping {sleep_time}s...")
                    time.sleep(sleep_time)
                    self.consecutive_errors = 0
            else:
                logger.debug(f"Error analyzing {ticker}: {e}")

            return None

    def process_batch_parallel(
        self,
        tickers: List[str],
        resume: bool = True,
        min_price: float = 5.0,
        max_price: float = 10000.0,
        min_volume: int = 100000
    ) -> Dict:
        """Process batch with parallel workers.

        Args:
            tickers: List of tickers
            resume: Resume from progress
            min_price: Min price
            max_price: Max price
            min_volume: Min volume

        Returns:
            Results dict
        """
        logger.info("="*60)
        logger.info("OPTIMIZED BATCH PROCESSING STARTED")
        logger.info(f"Tickers: {len(tickers)}")
        logger.info(f"Workers: {self.max_workers}")
        logger.info(f"Rate: ~{self.max_workers / self.rate_limit_delay:.1f} TPS")
        logger.info(f"Est. time: {len(tickers) * self.rate_limit_delay / self.max_workers / 3600:.1f} hours")
        logger.info("="*60)

        # Fetch SPY
        if not self.fetch_spy_data():
            return {'error': 'Failed to fetch SPY'}

        # Load progress
        if resume:
            progress = self.load_progress()
            if progress:
                self.processed_tickers = set(progress['processed'])
                self.current_results = progress['results']

        remaining = [t for t in tickers if t not in self.processed_tickers]
        logger.info(f"Processing {len(remaining)} remaining tickers")

        start_time = time.time()
        all_analyses = self.current_results.copy()
        phase_results = []

        # Process in parallel batches
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(
                    self.analyze_single_stock,
                    ticker,
                    min_price,
                    max_price,
                    min_volume
                ): ticker
                for ticker in remaining
            }

            # Process completions
            completed = 0
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                completed += 1

                try:
                    analysis = future.result()

                    if analysis:
                        all_analyses.append(analysis)
                        phase_results.append({
                            'ticker': ticker,
                            'phase': analysis['phase_info']['phase']
                        })

                        # Success - reset consecutive errors and reduce backoff
                        self.consecutive_errors = 0
                        if self.backoff_delay > 0:
                            self.backoff_delay = max(0, self.backoff_delay - 0.1)  # Slowly reduce

                    self.processed_tickers.add(ticker)

                    # Progress logging
                    if completed % 50 == 0 or completed == 1:
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining_count = len(remaining) - completed
                        eta_seconds = remaining_count / rate if rate > 0 else 0
                        eta = str(timedelta(seconds=int(eta_seconds)))

                        error_rate = self.error_count / max(self.total_requests, 1) * 100
                        filter_rate = self.filtered_count / max(self.total_requests, 1) * 100

                        logger.info(
                            f"Progress: {len(self.processed_tickers)}/{len(tickers)} "
                            f"({len(self.processed_tickers)/len(tickers)*100:.1f}%) | "
                            f"Rate: {rate:.1f}/sec | "
                            f"Filtered: {filter_rate:.1f}% | Errors: {error_rate:.1f}% | "
                            f"ETA: {eta}"
                        )

                    # Save progress
                    if completed % self.batch_size == 0:
                        self.save_progress(tickers, all_analyses)

                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")

        # Final save
        self.save_progress(tickers, all_analyses)

        total_time = time.time() - start_time
        actual_rate = len(tickers) / total_time if total_time > 0 else 0

        logger.info("="*60)
        logger.info("OPTIMIZED BATCH PROCESSING COMPLETE")
        logger.info(f"Time: {str(timedelta(seconds=int(total_time)))}")
        logger.info(f"Processed: {len(tickers)} tickers")
        logger.info(f"Analyzed: {len(all_analyses)} stocks")
        logger.info(f"Filtered: {self.filtered_count} ({self.filtered_count / max(self.total_requests, 1) * 100:.1f}%)")
        logger.info(f"Actual rate: {actual_rate:.2f} TPS")
        logger.info(f"Error rate: {self.error_count / max(self.total_requests, 1) * 100:.1f}%")

        # Log filter breakdown
        if self.filter_reasons:
            logger.info("-"*60)
            logger.info("FILTER BREAKDOWN:")
            sorted_filters = sorted(self.filter_reasons.items(), key=lambda x: x[1], reverse=True)
            for reason, count in sorted_filters:
                pct = (count / self.filtered_count * 100) if self.filtered_count > 0 else 0
                logger.info(f"  {reason}: {count} ({pct:.1f}%)")

        # Log error breakdown
        if self.error_types:
            logger.info("-"*60)
            logger.info("ERROR BREAKDOWN:")
            sorted_errors = sorted(self.error_types.items(), key=lambda x: x[1], reverse=True)
            for error_type, count in sorted_errors:
                pct = (count / self.error_count * 100) if self.error_count > 0 else 0
                example_ticker, example_msg = self.error_examples[error_type]
                logger.info(f"  {error_type}: {count} ({pct:.1f}%)")
                logger.info(f"    Example: {example_ticker} - {example_msg[:100]}")

        logger.info("="*60)

        return {
            'analyses': all_analyses,
            'phase_results': phase_results,
            'total_processed': len(tickers),
            'total_analyzed': len(all_analyses),
            'processing_time_seconds': total_time,
            'actual_tps': actual_rate,
            'error_rate': self.error_count / max(self.total_requests, 1)
        }

    def clear_progress(self):
        """Clear saved progress."""
        if self.progress_file.exists():
            self.progress_file.unlink()
        self.processed_tickers.clear()
        self.current_results.clear()
        logger.info("Progress cleared")
