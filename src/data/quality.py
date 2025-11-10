"""Data quality validation and monitoring for stock data.

This module provides comprehensive data quality checks including:
- Freshness validation (detecting stale data)
- Completeness validation (missing fields, gaps in data)
- Anomaly detection (unrealistic values, price spikes, volume anomalies)
- Quality scoring and reporting
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
from sqlalchemy import func

from .storage import StockDatabase


logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for data quality issues."""
    CRITICAL = "critical"  # Blocks screening (missing required data)
    WARNING = "warning"    # May affect accuracy (stale data, minor anomalies)
    INFO = "info"          # Informational (minor completeness issues)


@dataclass
class DataQualityIssue:
    """Represents a single data quality issue."""
    ticker: str
    issue_type: str
    severity: IssueSeverity
    description: str
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of the issue."""
        return f"[{self.severity.value.upper()}] {self.ticker}: {self.description}"


@dataclass
class TickerQualityReport:
    """Quality report for a single ticker."""
    ticker: str
    overall_score: float = 0.0  # 0-100
    issues: List[DataQualityIssue] = field(default_factory=list)
    last_fundamental_update: Optional[datetime] = None
    last_price_update: Optional[datetime] = None
    fundamental_completeness: float = 0.0  # 0-100
    price_history_days: int = 0
    has_critical_issues: bool = False
    needs_refresh: bool = False

    def add_issue(self, issue: DataQualityIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)
        if issue.severity == IssueSeverity.CRITICAL:
            self.has_critical_issues = True

    def get_issues_by_severity(self, severity: IssueSeverity) -> List[DataQualityIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]


class DataQualityChecker:
    """Validates and monitors data quality for stock data."""

    # Configuration constants
    FUNDAMENTAL_STALE_DAYS = 7
    PRICE_STALE_DAYS = 2
    MIN_HISTORY_DAYS = 180
    MAX_SINGLE_DAY_CHANGE = 0.20  # 20% price change threshold
    VOLUME_SPIKE_MULTIPLIER = 5.0
    MAX_REASONABLE_PE = 500
    MAX_REASONABLE_PB = 100
    MIN_REASONABLE_PRICE = 0.01

    def __init__(self, db: StockDatabase):
        """Initialize the data quality checker.

        Args:
            db: Database instance to check
        """
        self.db = db
        logger.info("DataQualityChecker initialized")

    def check_ticker(self, ticker: str) -> TickerQualityReport:
        """Run comprehensive quality checks on a single ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            TickerQualityReport with all issues and scores
        """
        logger.info(f"Running quality checks for {ticker}")
        report = TickerQualityReport(ticker=ticker)

        # Get latest data
        fundamentals = self.db.get_latest_fundamentals(ticker)
        if not fundamentals:
            report.add_issue(DataQualityIssue(
                ticker=ticker,
                issue_type="missing_fundamentals",
                severity=IssueSeverity.CRITICAL,
                description="No fundamental data available"
            ))
            report.overall_score = 0.0
            report.needs_refresh = True
            return report

        # Get price history
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        price_history = self.db.get_price_history(
            ticker,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        # Update report metadata
        # 'date' is the fundamental data date from the fundamentals table
        fund_date = fundamentals.get('date')
        if fund_date:
            if isinstance(fund_date, str):
                report.last_fundamental_update = datetime.fromisoformat(fund_date)
            else:
                report.last_fundamental_update = fund_date

        if not price_history.empty:
            # Price history DataFrame uses 'Date' (capital D) column
            date_col = 'Date' if 'Date' in price_history.columns else 'date'
            report.last_price_update = pd.to_datetime(price_history[date_col].max())
            report.price_history_days = len(price_history)

        # Run all validation checks
        self._check_freshness(ticker, fundamentals, price_history, report)
        self._check_completeness(ticker, fundamentals, price_history, report)
        self._check_anomalies(ticker, fundamentals, price_history, report)

        # Calculate overall quality score
        report.overall_score = self._calculate_quality_score(report)

        # Determine if refresh is needed
        report.needs_refresh = (
            report.has_critical_issues or
            len(report.get_issues_by_severity(IssueSeverity.WARNING)) >= 3
        )

        logger.info(f"{ticker} quality score: {report.overall_score:.1f}/100, "
                   f"issues: {len(report.issues)}, needs_refresh: {report.needs_refresh}")

        return report

    def check_all_tickers(self) -> Dict[str, TickerQualityReport]:
        """Run quality checks on all tickers in the database.

        Returns:
            Dictionary mapping ticker to quality report
        """
        tickers = self.db.get_all_tickers()
        logger.info(f"Running quality checks on {len(tickers)} tickers")

        reports = {}
        for ticker in tickers:
            try:
                reports[ticker] = self.check_ticker(ticker)
            except Exception as e:
                logger.error(f"Error checking {ticker}: {e}")
                # Create error report
                error_report = TickerQualityReport(ticker=ticker)
                error_report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="check_error",
                    severity=IssueSeverity.CRITICAL,
                    description=f"Error during quality check: {str(e)}"
                ))
                error_report.overall_score = 0.0
                error_report.needs_refresh = True
                reports[ticker] = error_report

        return reports

    def _check_freshness(
        self,
        ticker: str,
        fundamentals: Dict[str, Any],
        price_history: pd.DataFrame,
        report: TickerQualityReport
    ) -> None:
        """Check data freshness."""
        now = datetime.now()

        # Check fundamental data freshness
        # Use 'date' field from fundamentals table
        fund_date = fundamentals.get('date')
        if fund_date:
            if isinstance(fund_date, str):
                last_updated = datetime.fromisoformat(fund_date)
            else:
                last_updated = fund_date

            days_old = (now - last_updated).days
            if days_old > self.FUNDAMENTAL_STALE_DAYS:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="stale_fundamentals",
                    severity=IssueSeverity.WARNING,
                    description=f"Fundamental data is {days_old} days old (threshold: {self.FUNDAMENTAL_STALE_DAYS} days)",
                    metadata={"days_old": days_old, "last_updated": last_updated.isoformat()}
                ))

        # Check price data freshness
        if not price_history.empty:
            # Price history DataFrame uses 'Date' (capital D) column
            date_col = 'Date' if 'Date' in price_history.columns else 'date'
            last_price_date = pd.to_datetime(price_history[date_col].max())
            days_old = (now - last_price_date).days

            # Account for weekends - only flag if older than threshold + 2 days
            effective_threshold = self.PRICE_STALE_DAYS
            if now.weekday() in [0, 6]:  # Monday or Sunday
                effective_threshold += 2

            if days_old > effective_threshold:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="stale_prices",
                    severity=IssueSeverity.WARNING,
                    description=f"Price data is {days_old} days old (threshold: {effective_threshold} days)",
                    metadata={"days_old": days_old, "last_price_date": last_price_date.isoformat()}
                ))
        else:
            report.add_issue(DataQualityIssue(
                ticker=ticker,
                issue_type="missing_prices",
                severity=IssueSeverity.CRITICAL,
                description="No price history available"
            ))

    def _check_completeness(
        self,
        ticker: str,
        fundamentals: Dict[str, Any],
        price_history: pd.DataFrame,
        report: TickerQualityReport
    ) -> None:
        """Check data completeness."""
        # Required fundamental fields
        required_fields = ['pe_ratio', 'pb_ratio', 'current_price']
        optional_fields = ['fcf_yield', 'debt_equity', 'market_cap', 'dividend_yield']

        missing_required = []
        missing_optional = []

        for field in required_fields:
            value = fundamentals.get(field)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                missing_required.append(field)

        for field in optional_fields:
            value = fundamentals.get(field)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                missing_optional.append(field)

        # Report missing required fields as critical
        if missing_required:
            report.add_issue(DataQualityIssue(
                ticker=ticker,
                issue_type="missing_required_fields",
                severity=IssueSeverity.CRITICAL,
                description=f"Missing required fields: {', '.join(missing_required)}",
                metadata={"missing_fields": missing_required}
            ))

        # Report missing optional fields as info
        if missing_optional:
            report.add_issue(DataQualityIssue(
                ticker=ticker,
                issue_type="missing_optional_fields",
                severity=IssueSeverity.INFO,
                description=f"Missing optional fields: {', '.join(missing_optional)}",
                metadata={"missing_fields": missing_optional}
            ))

        # Calculate completeness percentage
        total_fields = len(required_fields) + len(optional_fields)
        present_fields = total_fields - len(missing_required) - len(missing_optional)
        report.fundamental_completeness = (present_fields / total_fields) * 100

        # Check price history completeness
        if not price_history.empty:
            days_available = len(price_history)
            if days_available < self.MIN_HISTORY_DAYS:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="insufficient_history",
                    severity=IssueSeverity.WARNING,
                    description=f"Only {days_available} days of price history (minimum: {self.MIN_HISTORY_DAYS})",
                    metadata={"days_available": days_available, "days_required": self.MIN_HISTORY_DAYS}
                ))

            # Check for gaps in trading days
            date_col = 'Date' if 'Date' in price_history.columns else 'date'
            price_history = price_history.sort_values(date_col)
            dates = pd.to_datetime(price_history[date_col])
            date_diffs = dates.diff().dt.days

            # Gaps > 7 days (accounting for weekends and holidays)
            large_gaps = date_diffs[date_diffs > 7]
            if not large_gaps.empty:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="price_history_gaps",
                    severity=IssueSeverity.INFO,
                    description=f"Found {len(large_gaps)} gaps >7 days in price history",
                    metadata={"num_gaps": len(large_gaps), "max_gap_days": int(large_gaps.max())}
                ))

    def _check_anomalies(
        self,
        ticker: str,
        fundamentals: Dict[str, Any],
        price_history: pd.DataFrame,
        report: TickerQualityReport
    ) -> None:
        """Check for data anomalies."""
        # Check fundamental value anomalies
        pe_ratio = fundamentals.get('pe_ratio')
        if pe_ratio is not None and not pd.isna(pe_ratio):
            if pe_ratio < 0:
                # Negative P/E can be valid (losses) but flag for awareness
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="negative_pe",
                    severity=IssueSeverity.INFO,
                    description=f"Negative P/E ratio: {pe_ratio:.2f} (company may be unprofitable)",
                    metadata={"pe_ratio": pe_ratio}
                ))
            elif pe_ratio > self.MAX_REASONABLE_PE:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="extreme_pe",
                    severity=IssueSeverity.WARNING,
                    description=f"Extremely high P/E ratio: {pe_ratio:.2f} (may indicate data error)",
                    metadata={"pe_ratio": pe_ratio}
                ))

        pb_ratio = fundamentals.get('pb_ratio')
        if pb_ratio is not None and not pd.isna(pb_ratio):
            if pb_ratio > self.MAX_REASONABLE_PB:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="extreme_pb",
                    severity=IssueSeverity.WARNING,
                    description=f"Extremely high P/B ratio: {pb_ratio:.2f} (may indicate data error)",
                    metadata={"pb_ratio": pb_ratio}
                ))
            elif pb_ratio < 0:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="negative_pb",
                    severity=IssueSeverity.WARNING,
                    description=f"Negative P/B ratio: {pb_ratio:.2f} (company has negative book value)",
                    metadata={"pb_ratio": pb_ratio}
                ))

        current_price = fundamentals.get('current_price')
        if current_price is not None and not pd.isna(current_price):
            if current_price < self.MIN_REASONABLE_PRICE:
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="penny_stock",
                    severity=IssueSeverity.INFO,
                    description=f"Very low price: ${current_price:.4f} (penny stock)",
                    metadata={"current_price": current_price}
                ))

        # Check price history anomalies
        if not price_history.empty and len(price_history) > 1:
            date_col = 'Date' if 'Date' in price_history.columns else 'date'
            close_col = 'Close' if 'Close' in price_history.columns else 'close'
            volume_col = 'Volume' if 'Volume' in price_history.columns else 'volume'

            price_history = price_history.sort_values(date_col)

            # Calculate daily returns
            closes = price_history[close_col].values
            returns = (closes[1:] - closes[:-1]) / closes[:-1]

            # Flag large single-day changes (potential stock splits)
            large_changes = abs(returns) > self.MAX_SINGLE_DAY_CHANGE
            if large_changes.any():
                num_spikes = large_changes.sum()
                max_change = abs(returns).max()
                report.add_issue(DataQualityIssue(
                    ticker=ticker,
                    issue_type="price_spike",
                    severity=IssueSeverity.WARNING,
                    description=f"Found {num_spikes} price spike(s) >{self.MAX_SINGLE_DAY_CHANGE*100:.0f}% "
                               f"(max: {max_change*100:.1f}%) - possible stock split or data error",
                    metadata={"num_spikes": int(num_spikes), "max_change_pct": float(max_change * 100)}
                ))

            # Check volume anomalies
            volumes = price_history[volume_col].values
            if len(volumes) > 20:
                avg_volume = volumes.mean()
                if avg_volume > 0:
                    volume_ratios = volumes / avg_volume

                    # Flag extreme volume spikes
                    extreme_spikes = volume_ratios > self.VOLUME_SPIKE_MULTIPLIER
                    if extreme_spikes.any():
                        num_spikes = extreme_spikes.sum()
                        max_ratio = volume_ratios.max()
                        report.add_issue(DataQualityIssue(
                            ticker=ticker,
                            issue_type="volume_spike",
                            severity=IssueSeverity.INFO,
                            description=f"Found {num_spikes} volume spike(s) >{self.VOLUME_SPIKE_MULTIPLIER}x average "
                                       f"(max: {max_ratio:.1f}x)",
                            metadata={"num_spikes": int(num_spikes), "max_ratio": float(max_ratio)}
                        ))

                    # Flag zero volume days
                    zero_volume_days = (volumes == 0).sum()
                    if zero_volume_days > 0:
                        report.add_issue(DataQualityIssue(
                            ticker=ticker,
                            issue_type="zero_volume",
                            severity=IssueSeverity.WARNING,
                            description=f"Found {zero_volume_days} day(s) with zero volume",
                            metadata={"zero_volume_days": int(zero_volume_days)}
                        ))

    def _calculate_quality_score(self, report: TickerQualityReport) -> float:
        """Calculate overall quality score (0-100).

        Scoring breakdown:
        - Start with 100 points
        - Subtract points for each issue based on severity
        - Bonus for data completeness and history length
        """
        score = 100.0

        # Deduct points for issues
        for issue in report.issues:
            if issue.severity == IssueSeverity.CRITICAL:
                score -= 30
            elif issue.severity == IssueSeverity.WARNING:
                score -= 10
            elif issue.severity == IssueSeverity.INFO:
                score -= 2

        # Bonus for completeness (up to +10 points)
        completeness_bonus = (report.fundamental_completeness / 100) * 10
        score += completeness_bonus

        # Bonus for sufficient history (up to +10 points)
        if report.price_history_days >= self.MIN_HISTORY_DAYS:
            history_bonus = min(10, (report.price_history_days / self.MIN_HISTORY_DAYS) * 5)
            score += history_bonus

        # Clamp to 0-100
        return max(0.0, min(100.0, score))

    def generate_summary_report(self, reports: Dict[str, TickerQualityReport]) -> str:
        """Generate human-readable summary report.

        Args:
            reports: Dictionary of ticker quality reports

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("DATA QUALITY SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Tickers Analyzed: {len(reports)}\n")

        # Overall statistics
        scores = [r.overall_score for r in reports.values()]
        avg_score = sum(scores) / len(scores) if scores else 0
        tickers_needing_refresh = sum(1 for r in reports.values() if r.needs_refresh)
        tickers_with_critical = sum(1 for r in reports.values() if r.has_critical_issues)

        lines.append("Overall Statistics:")
        lines.append(f"  Average Quality Score: {avg_score:.1f}/100")
        lines.append(f"  Tickers Needing Refresh: {tickers_needing_refresh} ({tickers_needing_refresh/len(reports)*100:.0f}%)")
        lines.append(f"  Tickers with Critical Issues: {tickers_with_critical} ({tickers_with_critical/len(reports)*100:.0f}%)")

        # Categorize tickers by quality
        excellent = [t for t, r in reports.items() if r.overall_score >= 90]
        good = [t for t, r in reports.items() if 70 <= r.overall_score < 90]
        fair = [t for t, r in reports.items() if 50 <= r.overall_score < 70]
        poor = [t for t, r in reports.items() if r.overall_score < 50]

        lines.append(f"\nQuality Distribution:")
        lines.append(f"  Excellent (90-100): {len(excellent)} tickers - {excellent}")
        lines.append(f"  Good (70-89):       {len(good)} tickers - {good}")
        lines.append(f"  Fair (50-69):       {len(fair)} tickers - {fair}")
        lines.append(f"  Poor (0-49):        {len(poor)} tickers - {poor}")

        # Detail section for each ticker
        lines.append("\n" + "=" * 80)
        lines.append("DETAILED TICKER REPORTS")
        lines.append("=" * 80)

        # Sort by quality score (worst first)
        sorted_reports = sorted(reports.items(), key=lambda x: x[1].overall_score)

        for ticker, report in sorted_reports:
            lines.append(f"\n{ticker} - Quality Score: {report.overall_score:.1f}/100")
            lines.append("-" * 80)

            # Status
            if report.overall_score >= 90:
                status = "✓ EXCELLENT - Ready for screening"
            elif report.overall_score >= 70:
                status = "✓ GOOD - Ready for screening"
            elif report.overall_score >= 50:
                status = "⚠ FAIR - Usable with caution"
            else:
                status = "✗ POOR - Needs refresh"

            lines.append(f"Status: {status}")

            # Metadata
            if report.last_fundamental_update:
                lines.append(f"Last Fundamental Update: {report.last_fundamental_update.strftime('%Y-%m-%d')}")
            if report.last_price_update:
                lines.append(f"Last Price Update: {report.last_price_update.strftime('%Y-%m-%d')}")
            lines.append(f"Price History Days: {report.price_history_days}")
            lines.append(f"Fundamental Completeness: {report.fundamental_completeness:.0f}%")

            # Issues
            if report.issues:
                lines.append(f"\nIssues Found ({len(report.issues)}):")
                critical = report.get_issues_by_severity(IssueSeverity.CRITICAL)
                warnings = report.get_issues_by_severity(IssueSeverity.WARNING)
                info = report.get_issues_by_severity(IssueSeverity.INFO)

                if critical:
                    lines.append(f"  CRITICAL ({len(critical)}):")
                    for issue in critical:
                        lines.append(f"    - {issue.description}")

                if warnings:
                    lines.append(f"  WARNINGS ({len(warnings)}):")
                    for issue in warnings:
                        lines.append(f"    - {issue.description}")

                if info:
                    lines.append(f"  INFO ({len(info)}):")
                    for issue in info:
                        lines.append(f"    - {issue.description}")
            else:
                lines.append("\nNo issues found - Data quality is excellent!")

            # Recommendation
            if report.needs_refresh:
                lines.append("\n⟳ RECOMMENDATION: Re-fetch data for this ticker")

        # Summary recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)

        if tickers_needing_refresh > 0:
            refresh_list = [t for t, r in reports.items() if r.needs_refresh]
            lines.append(f"\nTickers to refresh ({len(refresh_list)}):")
            lines.append(f"  {', '.join(refresh_list)}")
        else:
            lines.append("\n✓ All tickers have acceptable data quality!")

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)

    def save_quality_log(self, reports: Dict[str, TickerQualityReport]) -> None:
        """Save quality check results to database.

        Args:
            reports: Dictionary of ticker quality reports
        """
        logger.info(f"Saving quality log for {len(reports)} tickers")

        from sqlalchemy import text

        with self.db.engine.begin() as conn:
            for ticker, report in reports.items():
                # Insert quality log entry (convert booleans to int for SQLite)
                conn.execute(
                    text("""
                        INSERT INTO data_quality_log
                        (ticker, check_date, overall_score, has_critical_issues,
                         needs_refresh, num_issues, issue_summary)
                        VALUES (:ticker, :check_date, :score, :critical,
                                :refresh, :num_issues, :summary)
                    """),
                    {
                        "ticker": ticker,
                        "check_date": datetime.now(),
                        "score": report.overall_score,
                        "critical": 1 if report.has_critical_issues else 0,
                        "refresh": 1 if report.needs_refresh else 0,
                        "num_issues": len(report.issues),
                        "summary": "; ".join([issue.description for issue in report.issues[:5]])  # First 5 issues
                    }
                )

        logger.info("Quality log saved successfully")
