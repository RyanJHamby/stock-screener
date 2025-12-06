#!/usr/bin/env python3
"""Position management tool - integrates Robinhood positions with stop loss recommendations.

Fetches your current Robinhood positions and analyzes each one to recommend:
- When to trail stops up
- Exact new stop loss levels
- When to take partial profits
- Warnings for Phase 3/4 transitions

ONLY analyzes SHORT-TERM positions (held <1 year) to avoid disrupting long-term tax treatment.

Usage:
    python manage_positions.py
    python manage_positions.py --export  # Save report to file
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

from src.data.robinhood_positions import RobinhoodPositionFetcher, ROBINHOOD_AVAILABLE
from src.analysis.position_manager import PositionManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Position Management with Stop Loss Recommendations')
    parser.add_argument('--export', action='store_true', help='Export report to file')
    parser.add_argument('--entry-dates', type=str, help='JSON file with entry dates (optional)')
    args = parser.parse_args()

    if not ROBINHOOD_AVAILABLE:
        print("\n" + "="*80)
        print("ERROR: robin_stocks library not installed")
        print("="*80)
        print("\nInstall with:")
        print("  pip install robin-stocks")
        print("="*80)
        sys.exit(1)

    print("\n" + "="*80)
    print("POSITION MANAGEMENT - STOP LOSS RECOMMENDATIONS")
    print("="*80)
    print("\nThis tool will:")
    print("  ✓ Fetch your current Robinhood positions")
    print("  ✓ Analyze each position's technical structure")
    print("  ✓ Recommend stop loss adjustments for SHORT-TERM holdings")
    print("  ✓ Identify when to take partial profits")
    print("  ⚠️  LONG-TERM positions (1+ years) are EXCLUDED")
    print("      (to preserve favorable capital gains tax treatment)")
    print("\n" + "="*80 + "\n")

    # Initialize Robinhood fetcher
    try:
        fetcher = RobinhoodPositionFetcher()
    except ValueError as e:
        print(f"\nERROR: {e}\n")
        print("Set environment variable:")
        print("  export ROBINHOOD_USERNAME='your_email@example.com'")
        print("\nPassword and SMS MFA will be prompted (never stored)")
        sys.exit(1)
    except ImportError as e:
        print(f"\nERROR: {e}\n")
        sys.exit(1)

    # Login to Robinhood (will prompt for password and SMS MFA)
    print("Logging in to Robinhood...")
    if not fetcher.login():
        print("\n✗ Login failed. Check credentials.")
        sys.exit(1)

    try:
        # Fetch positions
        print("Fetching positions...\n")
        positions = fetcher.fetch_positions()

        if not positions:
            print("="*80)
            print("No open positions found")
            print("="*80)
            return

        print(f"✓ Found {len(positions)} positions\n")

        # Load entry dates if provided
        entry_dates = None
        if args.entry_dates:
            import json
            try:
                with open(args.entry_dates, 'r') as f:
                    dates_data = json.load(f)
                    # Convert string dates to datetime
                    from datetime import datetime as dt
                    entry_dates = {
                        ticker: dt.fromisoformat(date_str)
                        for ticker, date_str in dates_data.items()
                    }
                print(f"✓ Loaded entry dates for {len(entry_dates)} tickers\n")
            except Exception as e:
                print(f"⚠️  Could not load entry dates: {e}")
                print("Proceeding without entry date data (will not filter by tax treatment)\n")

        # Analyze positions
        print("Analyzing positions and calculating stop recommendations...\n")
        manager = PositionManager()
        analysis = manager.analyze_portfolio(positions, entry_dates)

        # Generate report
        report = manager.format_portfolio_report(analysis)
        print(report)

        # Export if requested
        if args.export:
            output_dir = Path("./data/position_reports")
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = output_dir / f"position_management_{timestamp}.txt"

            with open(filename, 'w') as f:
                f.write(report)

            print(f"\n✓ Report exported to: {filename}")

    finally:
        fetcher.logout()
        print("\n✓ Logged out from Robinhood\n")


if __name__ == '__main__':
    main()
