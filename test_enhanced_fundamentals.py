#!/usr/bin/env python3
"""Test script for enhanced fundamentals integration.

This script demonstrates the EnhancedFundamentalsFetcher in action.
"""

import os
from src.data.enhanced_fundamentals import EnhancedFundamentalsFetcher


def main():
    print("=" * 80)
    print("ENHANCED FUNDAMENTALS INTEGRATION TEST")
    print("=" * 80)
    print()

    # Initialize fetcher
    fetcher = EnhancedFundamentalsFetcher()

    # Check FMP status
    print("FMP Status:")
    print(f"  API Key Set: {'Yes' if os.getenv('FMP_API_KEY') else 'No'}")
    print(f"  FMP Available: {fetcher.fmp_available}")
    print()

    # Test ticker
    ticker = "AAPL"
    print(f"Testing with {ticker}...")
    print()

    # Test 1: Fetch with yfinance
    print("-" * 80)
    print("TEST 1: Fetch with yfinance (use_fmp=False)")
    print("-" * 80)
    try:
        data_yf = fetcher.fetch_quarterly_data(ticker, use_fmp=False)
        if data_yf:
            print(f"✓ Data source: {data_yf.get('data_source', 'yfinance')}")
            print(f"✓ Has revenue: {'Yes' if 'revenue_yoy_change' in data_yf else 'No'}")
            print(f"✓ Has EPS: {'Yes' if 'eps_yoy_change' in data_yf else 'No'}")
            print(f"✓ Has gross margin: {'Yes' if 'gross_margin' in data_yf else 'No'}")
            print(f"✗ Has net margin: {'Yes' if 'net_margin' in data_yf else 'No (yfinance limitation)'}")
            print(f"✗ Has operating margin: {'Yes' if 'operating_margin' in data_yf else 'No (yfinance limitation)'}")
        else:
            print("⚠ No data returned (yfinance may be temporarily unavailable)")
    except Exception as e:
        print(f"✗ Error: {e}")
    print()

    # Test 2: Try with FMP
    print("-" * 80)
    print("TEST 2: Attempt fetch with FMP (use_fmp=True)")
    print("-" * 80)
    if fetcher.fmp_available:
        try:
            data_fmp = fetcher.fetch_quarterly_data(ticker, use_fmp=True)
            if data_fmp:
                print(f"✓ Data source: {data_fmp.get('data_source', 'unknown')}")
                print(f"✓ Has revenue: {'Yes' if 'revenue_yoy_change' in data_fmp else 'No'}")
                print(f"✓ Has EPS: {'Yes' if 'eps_yoy_change' in data_fmp else 'No'}")
                print(f"✓ Has gross margin: {'Yes' if 'gross_margin' in data_fmp else 'No'}")
                print(f"✓ Has net margin: {'Yes' if 'net_margin' in data_fmp else 'No'}")
                print(f"✓ Has operating margin: {'Yes' if 'operating_margin' in data_fmp else 'No'}")
            else:
                print("⚠ No data returned from FMP, falling back to yfinance")
        except Exception as e:
            print(f"✗ FMP error (falling back to yfinance): {e}")
    else:
        print("⚠ FMP not available (FMP_API_KEY not set)")
        print()
        print("To enable FMP:")
        print("  1. Get free API key: https://site.financialmodelingprep.com/")
        print("  2. Add to .env: echo 'FMP_API_KEY=your_key' >> .env")
        print("  3. Source .env: source .env")
        print()
    print()

    # Test 3: Create snapshot
    print("-" * 80)
    print("TEST 3: Create fundamental snapshot")
    print("-" * 80)
    try:
        snapshot = fetcher.create_snapshot(ticker, use_fmp=False)
        print(snapshot)
    except Exception as e:
        print(f"✗ Error creating snapshot: {e}")
    print()

    # Show usage stats
    print("-" * 80)
    print("FMP API USAGE STATS")
    print("-" * 80)
    usage = fetcher.get_api_usage()
    print(f"  FMP Available: {usage['fmp_available']}")
    print(f"  Calls Used: {usage['fmp_calls_used']}/{usage['fmp_daily_limit']}")
    print(f"  Calls Remaining: {usage['fmp_calls_remaining']}")
    print()

    print("=" * 80)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 80)
    print()
    print("Next Steps:")
    print("  1. Set up FMP (see SETUP_FMP.md) for enhanced fundamentals")
    print("  2. Run full scan with: python run_optimized_scan.py --use-fmp")
    print("  3. Review ENHANCED_FUNDAMENTALS_USAGE.md for details")
    print()


if __name__ == '__main__':
    main()
