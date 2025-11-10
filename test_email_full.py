#!/usr/bin/env python3
"""Test script to fetch data, screen stocks, and send email notification."""

from src.data.fetcher import YahooFinanceFetcher
from src.data.storage import StockDatabase
from src.screening.screener import screen_candidates
from src.notifications.email_notifier import EmailNotifier
from dotenv import load_dotenv

load_dotenv()

# Initialize database and fetcher
db = StockDatabase()
fetcher = YahooFinanceFetcher()

# Define tickers to test
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

# Fetch data for all tickers
print(f"Fetching data for {len(tickers)} stocks...")
fundamentals_df, prices_df = fetcher.fetch_multiple(tickers, period="5y")

# Save to database
if not fundamentals_df.empty:
    print(f"\nSaving {len(fundamentals_df)} stocks to database...")
    for _, row in fundamentals_df.iterrows():
        ticker = row['ticker']
        db.save_stock_fundamentals(ticker, row.to_dict())

    # Save price history
    for ticker in tickers:
        ticker_prices = prices_df[prices_df['ticker'] == ticker].copy()
        if not ticker_prices.empty:
            ticker_prices = ticker_prices.drop('ticker', axis=1)
            db.save_price_history(ticker, ticker_prices)

    print("Data saved successfully!")
else:
    print("No data fetched!")
    exit(1)

print("\nScreening candidates...")
results = screen_candidates(db, tickers)

if not results.empty:
    print(f"Found {len(results)} results. Sending email...")

    # Send email
    notifier = EmailNotifier()
    success = notifier.send_screening_results(results=results, top_n=10)

    if success:
        print('✅ Email sent successfully! Check your inbox.')
    else:
        print('❌ Email failed to send')
else:
    print('❌ No screening results to send')
