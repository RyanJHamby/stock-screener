#!/usr/bin/env python3
"""Optimized full market scanner with parallel processing.

This version uses parallel workers to achieve 10-25 TPS safely while
avoiding rate limits through:
- Thread pool with 5 workers
- Per-worker rate limiting (0.2s = 5 TPS each)
- Adaptive backoff on errors
- Session pooling

Expected runtime: 15-30 minutes for 3,800+ stocks

Usage:
    python run_optimized_scan.py
    python run_optimized_scan.py --workers 10  # Faster but riskier
    python run_optimized_scan.py --conservative  # Slower but safer (3 workers)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.data.universe_fetcher import USStockUniverseFetcher
from src.screening.optimized_batch_processor import OptimizedBatchProcessor
from src.screening.benchmark import (
    analyze_spy_trend,
    calculate_market_breadth,
    format_benchmark_summary,
    should_generate_signals
)
from src.screening.signal_engine import score_buy_signal, score_sell_signal
from src.data.enhanced_fundamentals import EnhancedFundamentalsFetcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def save_report(results, buy_signals, sell_signals, spy_analysis, breadth, output_dir="./data/daily_scans"):
    """Save comprehensive report."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    date_str = datetime.now().strftime('%Y-%m-%d')

    output = []
    output.append("="*80)
    output.append("OPTIMIZED FULL MARKET SCAN - ALL US STOCKS")
    output.append(f"Scan Date: {date_str}")
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("="*80)
    output.append("")

    # Stats
    output.append("SCANNING STATISTICS")
    output.append("-"*80)
    output.append(f"Total Universe: {results['total_processed']:,} stocks")
    output.append(f"Analyzed: {results['total_analyzed']:,} stocks")
    output.append(f"Processing Time: {results['processing_time_seconds']/60:.1f} minutes")
    output.append(f"Actual TPS: {results['actual_tps']:.2f}")
    output.append(f"Error Rate: {results['error_rate']*100:.2f}%")
    output.append(f"Buy Signals: {len(buy_signals)}")
    output.append(f"Sell Signals: {len(sell_signals)}")
    output.append("")

    # Benchmark
    output.append(format_benchmark_summary(spy_analysis, breadth))
    output.append("")

    # Buy signals
    output.append("="*80)
    output.append(f"TOP BUY SIGNALS (Score >= 60) - {len(buy_signals)} Total")
    output.append("="*80)
    output.append("")

    if buy_signals:
        for i, signal in enumerate(buy_signals[:50], 1):
            output.append(f"\n{'#'*80}")
            output.append(f"BUY #{i}: {signal['ticker']} | Score: {signal['score']}/100")
            output.append(f"{'#'*80}")
            output.append(f"Phase: {signal['phase']}")
            if signal.get('breakout_price'):
                output.append(f"Breakout: ${signal['breakout_price']:.2f}")
            details = signal.get('details', {})
            if 'rs_slope' in details:
                output.append(f"RS: {details['rs_slope']:.3f}")
            if 'volume_ratio' in details:
                output.append(f"Volume: {details['volume_ratio']:.1f}x")
            output.append("\nReasons:")
            for reason in signal['reasons'][:5]:
                output.append(f"  • {reason}")
            if signal.get('fundamental_snapshot'):
                output.append(signal['fundamental_snapshot'])

        if len(buy_signals) > 50:
            output.append(f"\n{'='*80}")
            output.append(f"ADDITIONAL BUYS ({len(buy_signals)-50} more)")
            output.append(f"{'='*80}\n")
            remaining = [s['ticker'] for s in buy_signals[50:]]
            for i in range(0, len(remaining), 10):
                output.append(", ".join(remaining[i:i+10]))
    else:
        output.append("✗ NO BUY SIGNALS TODAY")

    # Sell signals
    output.append(f"\n\n{'='*80}")
    output.append(f"TOP SELL SIGNALS (Score >= 60) - {len(sell_signals)} Total")
    output.append(f"{'='*80}")
    output.append("")

    if sell_signals:
        for i, signal in enumerate(sell_signals[:30], 1):
            output.append(f"\n{'#'*80}")
            output.append(f"SELL #{i}: {signal['ticker']} | Score: {signal['score']}/100")
            output.append(f"{'#'*80}")
            output.append(f"Phase: {signal['phase']} | Severity: {signal['severity'].upper()}")
            if signal.get('breakdown_level'):
                output.append(f"Breakdown: ${signal['breakdown_level']:.2f}")
            details = signal.get('details', {})
            if 'rs_slope' in details:
                output.append(f"RS: {details['rs_slope']:.3f}")
            output.append("\nReasons:")
            for reason in signal['reasons'][:5]:
                output.append(f"  • {reason}")

        if len(sell_signals) > 30:
            output.append(f"\n{'='*80}")
            output.append(f"ADDITIONAL SELLS ({len(sell_signals)-30} more)")
            output.append(f"{'='*80}\n")
            remaining = [s['ticker'] for s in sell_signals[30:]]
            for i in range(0, len(remaining), 10):
                output.append(", ".join(remaining[i:i+10]))
    else:
        output.append("✗ NO SELL SIGNALS TODAY")

    output.append(f"\n\n{'='*80}")
    output.append("END OF SCAN")
    output.append(f"{'='*80}\n")

    report_text = "\n".join(output)

    # Save
    filepath = Path(output_dir) / f"optimized_scan_{timestamp}.txt"
    with open(filepath, 'w') as f:
        f.write(report_text)

    latest_path = Path(output_dir) / "latest_optimized_scan.txt"
    with open(latest_path, 'w') as f:
        f.write(report_text)

    logger.info(f"Report saved: {filepath}")
    print(report_text)

    return filepath


def main():
    parser = argparse.ArgumentParser(description='Optimized Full Market Scanner')
    parser.add_argument('--workers', type=int, default=3, help='Parallel workers (default: 3)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay per worker (default: 0.5s)')
    parser.add_argument('--conservative', action='store_true', help='Ultra-conservative mode (2 workers, 1.0s delay)')
    parser.add_argument('--aggressive', action='store_true', help='Faster mode (5 workers, 0.3s delay) - MAY HIT RATE LIMITS!')
    parser.add_argument('--resume', action='store_true', help='Resume from progress')
    parser.add_argument('--clear-progress', action='store_true', help='Clear progress')
    parser.add_argument('--test-mode', action='store_true', help='Test with 100 stocks')
    parser.add_argument('--min-price', type=float, default=5.0, help='Min price')
    parser.add_argument('--min-volume', type=int, default=100000, help='Min volume')
    parser.add_argument('--use-fmp', action='store_true', help='Use FMP for enhanced fundamentals on buy signals')
    parser.add_argument('--git-storage', action='store_true', help='Use Git-based storage for fundamentals (recommended)')

    args = parser.parse_args()

    # Presets
    if args.conservative:
        args.workers = 2
        args.delay = 1.0
        logger.info("Ultra-conservative mode: 2 workers, 1.0s delay (~2 TPS)")
    elif args.aggressive:
        args.workers = 5
        args.delay = 0.3
        logger.warning("Aggressive mode: 5 workers, 0.3s delay (~17 TPS) - MAY HIT RATE LIMITS!")

    effective_tps = args.workers / args.delay
    logger.info(f"Configuration: {args.workers} workers × {1/args.delay:.1f} TPS = ~{effective_tps:.1f} TPS effective")

    # Initialize enhanced fundamentals fetcher
    fundamentals_fetcher = EnhancedFundamentalsFetcher()
    if args.use_fmp and fundamentals_fetcher.fmp_available:
        logger.info("FMP enabled - will use for buy signal fundamentals")
    elif args.use_fmp:
        logger.warning("--use-fmp specified but FMP_API_KEY not set. Using yfinance only.")

    try:
        # Fetch universe
        universe_fetcher = USStockUniverseFetcher()
        logger.info("Fetching stock universe...")
        tickers = universe_fetcher.fetch_universe()

        if not tickers:
            logger.error("Failed to fetch universe")
            sys.exit(1)

        logger.info(f"Universe: {len(tickers):,} stocks")

        if args.test_mode:
            tickers = tickers[:100]
            logger.info(f"TEST MODE: {len(tickers)} stocks")

        # Initialize processor
        processor = OptimizedBatchProcessor(
            max_workers=args.workers,
            rate_limit_delay=args.delay,
            use_git_storage=args.git_storage
        )

        if args.git_storage:
            logger.info("Git-based fundamental storage enabled - 74% API call reduction!")

        if args.clear_progress:
            processor.clear_progress()

        # Process
        results = processor.process_batch_parallel(
            tickers,
            resume=args.resume,
            min_price=args.min_price,
            min_volume=args.min_volume
        )

        if 'error' in results:
            logger.error(results['error'])
            sys.exit(1)

        # Analysis
        logger.info("Generating signals...")
        spy_analysis = analyze_spy_trend(processor.spy_data, processor.spy_price)
        breadth = calculate_market_breadth(results['phase_results'])
        signal_rec = should_generate_signals(spy_analysis, breadth)

        # Buy signals
        buy_signals = []
        if signal_rec['should_generate_buys']:
            for analysis in results['analyses']:
                if analysis['phase_info']['phase'] in [1, 2]:
                    signal = score_buy_signal(
                        ticker=analysis['ticker'],
                        price_data=analysis['price_data'],
                        current_price=analysis['current_price'],
                        phase_info=analysis['phase_info'],
                        rs_series=analysis['rs_series'],
                        fundamentals=analysis.get('fundamental_analysis')
                    )
                    if signal['is_buy']:
                        # Use FMP for enhanced snapshot if requested and available
                        signal['fundamental_snapshot'] = fundamentals_fetcher.create_snapshot(
                            analysis['ticker'],
                            quarterly_data=analysis.get('quarterly_data', {}),
                            use_fmp=args.use_fmp
                        )
                        buy_signals.append(signal)

        buy_signals = sorted(buy_signals, key=lambda x: x['score'], reverse=True)

        # Sell signals
        sell_signals = []
        if signal_rec['should_generate_sells']:
            for analysis in results['analyses']:
                if analysis['phase_info']['phase'] in [3, 4]:
                    signal = score_sell_signal(
                        ticker=analysis['ticker'],
                        price_data=analysis['price_data'],
                        current_price=analysis['current_price'],
                        phase_info=analysis['phase_info'],
                        rs_series=analysis['rs_series']
                    )
                    if signal['is_sell']:
                        sell_signals.append(signal)

        sell_signals = sorted(sell_signals, key=lambda x: x['score'], reverse=True)

        # Report
        save_report(results, buy_signals, sell_signals, spy_analysis, breadth)

        # Show FMP usage if enabled
        if args.use_fmp:
            usage = fundamentals_fetcher.get_api_usage()
            logger.info("="*60)
            logger.info("FMP API USAGE")
            logger.info(f"Calls used: {usage['fmp_calls_used']}/{usage['fmp_daily_limit']}")
            logger.info(f"Calls remaining: {usage['fmp_calls_remaining']}")
            if 'bandwidth_used_mb' in usage:
                logger.info(f"Bandwidth used: {usage['bandwidth_used_mb']:.1f} MB / {usage['bandwidth_limit_gb']:.1f} GB ({usage['bandwidth_pct_used']:.1f}%)")
                logger.info(f"Earnings season: {'Yes' if usage['is_earnings_season'] else 'No'} (cache: {usage['cache_hours']}h)")
            logger.info("="*60)

        logger.info("="*60)
        logger.info("SCAN COMPLETE")
        logger.info(f"Time: {results['processing_time_seconds']/60:.1f} minutes")
        logger.info(f"Actual TPS: {results['actual_tps']:.2f}")
        logger.info(f"Buy signals: {len(buy_signals)}")
        logger.info(f"Sell signals: {len(sell_signals)}")
        logger.info("="*60)

    except KeyboardInterrupt:
        logger.info("\nInterrupted - progress saved")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
