#!/usr/bin/env python3
"""Demo script showing the stock screener in action."""

import os
from src.data import YahooFinanceFetcher, StockDatabase

# Set environment for demo (use SQLite for simplicity)
os.environ['DATABASE_URL'] = 'sqlite:///./stock_screener_demo.db'


def main():
    """Run a demonstration of the stock screener."""
    print("=" * 70)
    print("Stock Screener Demo - Data Fetching & Storage")
    print("=" * 70)

    # Initialize components
    print("\n1. Initializing fetcher and database...")
    fetcher = YahooFinanceFetcher(cache_dir="./data/cache")
    db = StockDatabase()
    print("✓ Components initialized")

    # Sample tickers
    tickers = ["AAPL", "MSFT", "GOOGL"]
    print(f"\n2. Fetching data for {len(tickers)} stocks: {', '.join(tickers)}")

    # Fetch and save data
    for ticker in tickers:
        print(f"\n   Processing {ticker}...")

        # Fetch fundamentals
        fundamentals = fetcher.fetch_fundamentals(ticker)
        if fundamentals:
            print(f"   ✓ Fetched fundamentals for {ticker}")
            print(f"     - P/E Ratio: {fundamentals.get('pe_ratio')}")
            print(f"     - P/B Ratio: {fundamentals.get('pb_ratio')}")
            print(f"     - Current Price: ${fundamentals.get('current_price')}")

            # Save to database
            db.save_stock_fundamentals(ticker, fundamentals)
            print(f"   ✓ Saved fundamentals to database")

        # Fetch price history
        prices = fetcher.fetch_price_history(ticker, period="1mo")
        if not prices.empty:
            print(f"   ✓ Fetched {len(prices)} days of price history")
            db.save_price_history(ticker, prices)
            print(f"   ✓ Saved price history to database")

    # Query database
    print("\n3. Querying database...")
    all_tickers = db.get_all_tickers()
    print(f"   Database contains {len(all_tickers)} stocks: {', '.join(all_tickers)}")

    # Get latest fundamentals
    print("\n4. Retrieving latest fundamentals from database:")
    for ticker in all_tickers:
        data = db.get_latest_fundamentals(ticker)
        if data:
            print(f"\n   {ticker} - {data.get('name')}")
            print(f"   Sector: {data.get('sector')}")
            print(f"   P/E: {data.get('pe_ratio'):.2f}" if data.get('pe_ratio') else "   P/E: N/A")
            print(f"   P/B: {data.get('pb_ratio'):.2f}" if data.get('pb_ratio') else "   P/B: N/A")
            print(f"   Price: ${data.get('current_price'):.2f}" if data.get('current_price') else "   Price: N/A")

    # Screen for value stocks
    print("\n5. Screening for value stocks (P/E < 30, P/B < 50)...")
    value_stocks = db.query_cheap_stocks(pe_max=30, pb_max=50)
    if value_stocks:
        print(f"   Found {len(value_stocks)} value stocks: {', '.join(value_stocks)}")
    else:
        print("   No stocks meet the criteria")

    # Cache statistics
    print("\n6. Cache statistics:")
    cache_files = list(fetcher.cache_dir.glob("*.pkl"))
    print(f"   Cache contains {len(cache_files)} files")
    print(f"   Cache directory: {fetcher.cache_dir}")

    print("\n" + "=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)
    print("\nNext steps:")
    print("- Check the database: stock_screener_demo.db")
    print("- Explore the cache: ./data/cache/")
    print("- Run again to see cache in action (instant responses!)")
    print("- Modify the script to fetch more stocks or different time periods")


if __name__ == "__main__":
    main()
