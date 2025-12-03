#!/usr/bin/env python3
"""Quick script to check your current Robinhood positions.

Usage:
    python check_positions.py

This script:
- ✓ Fetches your current stock positions (tickers + entry prices)
- ✗ Does NOT read account balances
- ✗ Does NOT execute any trades
- ✗ Does NOT modify positions

Requires:
    pip install robin-stocks

Environment variables:
    ROBINHOOD_USERNAME=your_email@example.com
    ROBINHOOD_PASSWORD=your_password
    ROBINHOOD_MFA_CODE=123456  # Optional if 2FA enabled
"""

import sys
import logging
from src.data.robinhood_positions import RobinhoodPositionFetcher, ROBINHOOD_AVAILABLE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    if not ROBINHOOD_AVAILABLE:
        print("\n" + "="*60)
        print("ERROR: robin_stocks library not installed")
        print("="*60)
        print("\nInstall with:")
        print("  pip install robin-stocks")
        print("\nThis library provides READ-ONLY access to your positions.")
        print("="*60)
        sys.exit(1)

    print("\n" + "="*60)
    print("ROBINHOOD POSITION CHECKER (Read-Only)")
    print("="*60)
    print("\nThis will:")
    print("  ✓ Fetch tickers and entry prices of your current positions")
    print("  ✗ NOT read account balance or portfolio value")
    print("  ✗ NOT execute any trades or modifications")
    print("\n" + "="*60 + "\n")

    # Initialize fetcher
    try:
        fetcher = RobinhoodPositionFetcher()
    except ValueError as e:
        print(f"\nERROR: {e}\n")
        print("Set these environment variables:")
        print("  export ROBINHOOD_USERNAME='your_email@example.com'")
        print("  export ROBINHOOD_PASSWORD='your_password'")
        print("  export ROBINHOOD_MFA_CODE='123456'  # Optional if using 2FA")
        print("\nOr add them to your .env file")
        sys.exit(1)
    except ImportError as e:
        print(f"\nERROR: {e}\n")
        sys.exit(1)

    # Login
    print("Logging in to Robinhood...")
    mfa_code = input("Enter MFA code (press Enter to skip if no 2FA): ").strip()
    mfa_code = mfa_code if mfa_code else None

    if not fetcher.login(mfa_code):
        print("\n✗ Login failed. Check your credentials.")
        sys.exit(1)

    try:
        # Fetch positions
        print("\nFetching positions...\n")
        positions = fetcher.fetch_positions()

        if not positions:
            print("="*60)
            print("No open positions found")
            print("="*60)
            return

        # Display formatted report
        print(fetcher.format_positions_report())

        # Export option
        export = input("\nExport to file? (y/n): ").strip().lower()
        if export == 'y':
            from datetime import datetime
            filename = f"robinhood_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            with open(filename, 'w') as f:
                f.write(fetcher.format_positions_report())

            print(f"\n✓ Exported to: {filename}")

    finally:
        fetcher.logout()
        print("\n✓ Logged out\n")


if __name__ == '__main__':
    main()
