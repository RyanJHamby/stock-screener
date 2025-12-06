#!/usr/bin/env python3
"""Automated position reporting - runs as part of GitHub Actions workflow.

This version:
- Uses stored credentials from environment (for automated runs)
- Fetches positions from Robinhood
- Generates stop loss recommendations using cached data
- Saves report to file
- Does NOT prompt for input (fully automated)

For manual runs on your machine, use: python manage_positions.py
For automated runs in GitHub Actions, use: python automated_position_report.py
"""

import sys
import logging
import os
from datetime import datetime
from pathlib import Path

# Only run if credentials are provided
username = os.getenv('ROBINHOOD_USERNAME')
password = os.getenv('ROBINHOOD_PASSWORD')

if not username or not password:
    print("ROBINHOOD credentials not set - skipping position analysis")
    print("To enable automated position reports, set:")
    print("  - ROBINHOOD_USERNAME in GitHub Secrets")
    print("  - ROBINHOOD_PASSWORD in GitHub Secrets")
    sys.exit(0)  # Exit gracefully, don't fail the build

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from src.data.robinhood_positions import RobinhoodPositionFetcher, ROBINHOOD_AVAILABLE
    from src.analysis.position_manager import PositionManager

    if not ROBINHOOD_AVAILABLE:
        logger.error("robin_stocks library not available")
        sys.exit(1)

    logger.info("Starting automated position analysis...")

    # Login (no prompts - uses environment variables)
    try:
        fetcher = RobinhoodPositionFetcher()
        logger.info(f"Logging in as {username}...")

        if not fetcher.login(password=password):
            logger.error("Failed to login to Robinhood")
            sys.exit(1)

        # Fetch positions
        logger.info("Fetching positions...")
        positions = fetcher.fetch_positions()
        fetcher.logout()

        if not positions:
            logger.info("No open positions found")
            sys.exit(0)

        logger.info(f"Found {len(positions)} positions")

        # Analyze using cached data (no extra API calls)
        logger.info("Analyzing positions using cached market data...")
        manager = PositionManager(use_cache=True)  # Use cache to avoid extra API calls
        analysis = manager.analyze_portfolio(positions)

        # Generate report
        report = manager.format_portfolio_report(analysis)

        # Save to file
        output_dir = Path("./data/position_reports")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f"position_management_{timestamp}.txt"

        with open(filename, 'w') as f:
            f.write(report)

        logger.info(f"✓ Report saved to {filename}")

        # Also print to stdout for GitHub Actions log
        print("\n" + report)

        logger.info("✓ Automated position analysis complete")

    except Exception as e:
        logger.error(f"Error during position analysis: {e}", exc_info=True)
        sys.exit(1)

except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Install dependencies with: pip install robin-stocks yfinance pandas")
    sys.exit(1)
