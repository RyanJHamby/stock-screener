#!/usr/bin/env python3
"""Demonstration of the data quality validation system.

This script shows how to use the DataQualityChecker to validate stock data
and identify quality issues that need attention.
"""

import os
import sys
from datetime import datetime

from src.data import StockDatabase, DataQualityChecker

# Use the main database
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'sqlite:///./stock_screener.db')


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def run_quality_checks():
    """Run data quality checks on all tickers in database."""
    print_separator()
    print("DATA QUALITY VALIDATION SYSTEM")
    print_separator()
    print(f"\nStarting quality checks at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Initialize database and quality checker
    print("Initializing database connection...")
    db = StockDatabase()

    print("Initializing quality checker...")
    checker = DataQualityChecker(db)

    # Get list of tickers
    tickers = db.get_all_tickers()
    print(f"\nFound {len(tickers)} tickers in database: {', '.join(tickers)}")

    if not tickers:
        print("\nNo tickers found in database. Please run the data fetcher first.")
        print("Example: python demo.py")
        return

    # Run quality checks
    print_separator()
    print("RUNNING QUALITY CHECKS")
    print_separator()

    print("\nChecking each ticker for:")
    print("  ✓ Data freshness (fundamentals, prices)")
    print("  ✓ Data completeness (required fields, history length)")
    print("  ✓ Data anomalies (extreme values, spikes, gaps)")
    print()

    reports = checker.check_all_tickers()

    # Generate and display summary report
    print_separator()
    print("GENERATING SUMMARY REPORT")
    print_separator()

    summary = checker.generate_summary_report(reports)
    print(summary)

    # Save quality log to database
    print_separator()
    print("SAVING QUALITY LOG")
    print_separator()

    try:
        checker.save_quality_log(reports)
        print("\n✓ Quality check results saved to database")
        print("  Table: data_quality_log")
    except Exception as e:
        print(f"\n⚠ Warning: Could not save quality log: {e}")
        print("  This is expected if the table doesn't exist yet.")
        print("  The database schema will be updated automatically on next run.")

    # Display actionable summary
    print_separator()
    print("ACTIONABLE SUMMARY")
    print_separator()

    tickers_needing_refresh = [t for t, r in reports.items() if r.needs_refresh]
    excellent_tickers = [t for t, r in reports.items() if r.overall_score >= 90]
    poor_tickers = [t for t, r in reports.items() if r.overall_score < 50]

    print(f"\n📊 Quality Overview:")
    print(f"  Total Tickers: {len(reports)}")
    print(f"  Excellent Quality (≥90): {len(excellent_tickers)}")
    print(f"  Poor Quality (<50): {len(poor_tickers)}")
    print(f"  Need Refresh: {len(tickers_needing_refresh)}")

    if excellent_tickers:
        print(f"\n✓ Ready for Screening ({len(excellent_tickers)} tickers):")
        for ticker in excellent_tickers:
            score = reports[ticker].overall_score
            print(f"  • {ticker:6s} - Score: {score:.1f}/100")

    if tickers_needing_refresh:
        print(f"\n⚠ Need Data Refresh ({len(tickers_needing_refresh)} tickers):")
        for ticker in tickers_needing_refresh:
            report = reports[ticker]
            from src.data import IssueSeverity
            critical_count = len([i for i in report.issues if i.severity == IssueSeverity.CRITICAL])
            warning_count = len([i for i in report.issues if i.severity == IssueSeverity.WARNING])
            print(f"  • {ticker:6s} - Score: {report.overall_score:.1f}/100 "
                  f"(Critical: {critical_count}, Warnings: {warning_count})")

        print("\nTo refresh data for these tickers:")
        print("```python")
        print("from src.data import YahooFinanceFetcher, StockDatabase")
        print()
        print("fetcher = YahooFinanceFetcher()")
        print("db = StockDatabase()")
        print()
        print(f"tickers = {tickers_needing_refresh}")
        print("for ticker in tickers:")
        print("    fundamentals = fetcher.fetch_fundamentals(ticker)")
        print("    if fundamentals:")
        print("        db.save_stock_fundamentals(ticker, fundamentals)")
        print("    prices = fetcher.fetch_price_history(ticker, period='1y')")
        print("    if not prices.empty:")
        print("        db.save_price_history(ticker, prices)")
        print("```")
    else:
        print("\n✓ All tickers have acceptable data quality!")

    # Display detailed issues for poor quality tickers
    if poor_tickers:
        print_separator()
        print("DETAILED ISSUES FOR POOR QUALITY TICKERS")
        print_separator()

        for ticker in poor_tickers:
            report = reports[ticker]
            print(f"\n{ticker} - Score: {report.overall_score:.1f}/100")
            print("-" * 40)

            for issue in report.issues:
                severity_icon = "🔴" if issue.severity.value == "critical" else "⚠️" if issue.severity.value == "warning" else "ℹ️"
                print(f"  {severity_icon} {issue.description}")

    # Final recommendations
    print_separator()
    print("NEXT STEPS")
    print_separator()

    print("\n1. Review Quality Report:")
    print("   - Identify which tickers are ready for screening")
    print("   - Note which tickers need data refresh")

    print("\n2. Refresh Data (if needed):")
    print("   - Run fetcher for tickers with quality issues")
    print("   - Re-run quality checks to verify improvements")

    print("\n3. Monitor Data Quality:")
    print("   - Run quality checks weekly before screening")
    print("   - Track quality scores over time using data_quality_log table")

    print("\n4. Integrate into Pipeline:")
    print("   - Add quality checks before running screener")
    print("   - Set up alerts for quality degradation")
    print("   - Automate data refresh for stale data")

    print_separator()


def check_single_ticker(ticker: str):
    """Run quality check on a single ticker.

    Args:
        ticker: Stock ticker symbol
    """
    print_separator()
    print(f"QUALITY CHECK: {ticker}")
    print_separator()

    db = StockDatabase()
    checker = DataQualityChecker(db)

    print(f"\nChecking data quality for {ticker}...\n")

    report = checker.check_ticker(ticker)

    # Display results
    print(f"Overall Quality Score: {report.overall_score:.1f}/100")
    print(f"Status: {'✓ PASS' if report.overall_score >= 70 else '✗ FAIL'}")
    print(f"Needs Refresh: {'Yes' if report.needs_refresh else 'No'}")

    if report.last_fundamental_update:
        days_old = (datetime.now() - report.last_fundamental_update).days
        print(f"\nLast Fundamental Update: {report.last_fundamental_update.strftime('%Y-%m-%d')} ({days_old} days ago)")

    if report.last_price_update:
        days_old = (datetime.now() - report.last_price_update).days
        print(f"Last Price Update: {report.last_price_update.strftime('%Y-%m-%d')} ({days_old} days ago)")

    print(f"Price History Days: {report.price_history_days}")
    print(f"Fundamental Completeness: {report.fundamental_completeness:.0f}%")

    if report.issues:
        print(f"\nIssues Found ({len(report.issues)}):")
        print("-" * 40)

        for severity in ["critical", "warning", "info"]:
            issues = [i for i in report.issues if i.severity.value == severity]
            if issues:
                icon = "🔴" if severity == "critical" else "⚠️" if severity == "warning" else "ℹ️"
                print(f"\n{icon} {severity.upper()} ({len(issues)}):")
                for issue in issues:
                    print(f"  • {issue.description}")
    else:
        print("\n✓ No issues found - Data quality is excellent!")

    print_separator()


def main():
    """Main demonstration function."""
    if len(sys.argv) > 1:
        # Check specific ticker
        ticker = sys.argv[1].upper()
        check_single_ticker(ticker)
    else:
        # Check all tickers
        run_quality_checks()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nQuality check interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
