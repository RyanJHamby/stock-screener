#!/usr/bin/env python3
"""Robinhood position fetcher - READ ONLY.

This module ONLY fetches your current stock positions (ticker + entry price).
It does NOT:
- Read account balances or portfolio value
- Execute any trades
- Modify any positions
- Access buying power or cash

Authentication: Uses robin_stocks library with MFA support.
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

try:
    import robin_stocks.robinhood as rh
    ROBINHOOD_AVAILABLE = True
except ImportError:
    ROBINHOOD_AVAILABLE = False

logger = logging.getLogger(__name__)


class RobinhoodPositionFetcher:
    """Fetch current stock positions from Robinhood (read-only)."""

    def __init__(self):
        """Initialize fetcher.

        Requires environment variable:
        - ROBINHOOD_USERNAME: Your Robinhood email

        Password and MFA will be prompted interactively (never stored).
        """
        if not ROBINHOOD_AVAILABLE:
            raise ImportError(
                "robin_stocks not installed. Install with: pip install robin-stocks"
            )

        self.username = os.getenv('ROBINHOOD_USERNAME')
        self.logged_in = False

        if not self.username:
            raise ValueError(
                "Missing ROBINHOOD_USERNAME environment variable. "
                "Set with: export ROBINHOOD_USERNAME='your_email@example.com'"
            )

    def login(self, password: Optional[str] = None, mfa_code: Optional[str] = None) -> bool:
        """Login to Robinhood with interactive password and SMS MFA.

        Args:
            password: Password (will prompt if not provided)
            mfa_code: SMS MFA code (will prompt if needed)

        Returns:
            True if login successful
        """
        try:
            logger.info("Logging into Robinhood (read-only mode)...")

            # Get password if not provided
            if not password:
                import getpass
                password = getpass.getpass(f"Robinhood password for {self.username}: ")

            # Initial login attempt (will trigger SMS if 2FA enabled)
            try:
                login_result = rh.login(self.username, password)

                if login_result:
                    self.logged_in = True
                    logger.info("✓ Robinhood login successful (no MFA required)")
                    return True

            except Exception as e:
                error_msg = str(e).lower()

                # Check if MFA is required
                if 'mfa' in error_msg or 'challenge' in error_msg or 'verification' in error_msg:
                    logger.info("MFA required - check your phone for SMS code from Robinhood")

                    # Prompt for SMS code if not provided
                    if not mfa_code:
                        mfa_code = input("Enter SMS code from Robinhood: ").strip()

                    # Try login with MFA
                    login_result = rh.login(
                        self.username,
                        password,
                        mfa_code=mfa_code,
                        by_sms=True
                    )

                    if login_result:
                        self.logged_in = True
                        logger.info("✓ Robinhood login successful with SMS MFA")
                        return True
                else:
                    raise e

            logger.error("✗ Robinhood login failed")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def fetch_positions(self) -> List[Dict]:
        """Fetch current stock positions (READ ONLY).

        Returns list of positions with:
        - ticker: Stock symbol
        - quantity: Number of shares (rounded to int)
        - average_buy_price: Average entry price
        - current_price: Latest market price
        - unrealized_pl_pct: Unrealized P/L percentage

        Does NOT include:
        - Account balance
        - Total portfolio value
        - Buying power
        - Any dollar amounts beyond per-share prices

        Returns:
            List of position dicts
        """
        if not self.logged_in:
            logger.error("Not logged in. Call login() first.")
            return []

        try:
            logger.info("Fetching current positions (read-only)...")

            # Get positions - this returns stocks you currently own
            positions = rh.get_open_stock_positions()

            if not positions:
                logger.info("No open positions found")
                return []

            result = []
            for position in positions:
                try:
                    # Extract basic position info (NO account balances)
                    quantity = float(position.get('quantity', 0))
                    if quantity <= 0:
                        continue

                    # Get instrument data to find ticker
                    instrument_url = position.get('instrument')
                    instrument_data = rh.get_instrument_by_url(instrument_url)
                    ticker = instrument_data.get('symbol', 'UNKNOWN')

                    # Get prices
                    avg_buy_price = float(position.get('average_buy_price', 0))

                    # Get current market price
                    current_price_data = rh.get_latest_price(ticker)
                    current_price = float(current_price_data[0]) if current_price_data else 0

                    # Calculate unrealized P/L %
                    if avg_buy_price > 0 and current_price > 0:
                        pl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100
                    else:
                        pl_pct = 0

                    result.append({
                        'ticker': ticker,
                        'quantity': int(round(quantity)),  # Round to whole shares
                        'average_buy_price': round(avg_buy_price, 2),
                        'current_price': round(current_price, 2),
                        'unrealized_pl_pct': round(pl_pct, 2)
                    })

                except Exception as e:
                    logger.warning(f"Error processing position: {e}")
                    continue

            logger.info(f"✓ Fetched {len(result)} positions")
            return result

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def logout(self):
        """Logout from Robinhood."""
        if self.logged_in:
            try:
                rh.logout()
                self.logged_in = False
                logger.info("Logged out from Robinhood")
            except Exception as e:
                logger.warning(f"Logout warning: {e}")

    def get_position_tickers(self) -> List[str]:
        """Get just the tickers of current positions.

        Useful for checking if you already own a stock before buying.

        Returns:
            List of ticker symbols
        """
        positions = self.fetch_positions()
        return [p['ticker'] for p in positions]

    def format_positions_report(self) -> str:
        """Format positions as a readable text report.

        Returns:
            Formatted string with position details
        """
        positions = self.fetch_positions()

        if not positions:
            return "No open positions"

        lines = []
        lines.append("="*60)
        lines.append("CURRENT ROBINHOOD POSITIONS (Read-Only)")
        lines.append(f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*60)
        lines.append("")

        for i, pos in enumerate(positions, 1):
            lines.append(f"{i}. {pos['ticker']}")
            lines.append(f"   Shares: {pos['quantity']}")
            lines.append(f"   Entry: ${pos['average_buy_price']:.2f}")
            lines.append(f"   Current: ${pos['current_price']:.2f}")

            pl_sign = "+" if pos['unrealized_pl_pct'] >= 0 else ""
            lines.append(f"   P/L: {pl_sign}{pos['unrealized_pl_pct']:.2f}%")
            lines.append("")

        lines.append("="*60)
        lines.append(f"Total positions: {len(positions)}")
        lines.append("="*60)

        return "\n".join(lines)


def main():
    """Example usage - fetch and display current positions."""
    import sys

    if not ROBINHOOD_AVAILABLE:
        print("ERROR: robin_stocks not installed")
        print("Install with: pip install robin-stocks")
        sys.exit(1)

    # Initialize fetcher
    try:
        fetcher = RobinhoodPositionFetcher()
    except ValueError as e:
        print(f"ERROR: {e}")
        print("\nSet environment variable:")
        print("  export ROBINHOOD_USERNAME='your_email@example.com'")
        print("\nPassword and MFA will be prompted (never stored in files)")
        sys.exit(1)

    # Login (will prompt for password and SMS MFA interactively)
    if not fetcher.login():
        print("Login failed. Check credentials.")
        sys.exit(1)

    try:
        # Fetch and display positions
        print("\n" + fetcher.format_positions_report())

        # Also show just tickers
        tickers = fetcher.get_position_tickers()
        print(f"\nTickers you currently own: {', '.join(tickers)}")

    finally:
        fetcher.logout()


if __name__ == '__main__':
    main()
