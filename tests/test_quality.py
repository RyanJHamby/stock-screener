"""Tests for data quality validation module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from src.data.quality import (
    DataQualityChecker,
    TickerQualityReport,
    DataQualityIssue,
    IssueSeverity
)
from src.data import StockDatabase


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = Mock(spec=StockDatabase)
    db.engine = MagicMock()
    return db


@pytest.fixture
def quality_checker(mock_db):
    """Create a DataQualityChecker instance with mock database."""
    return DataQualityChecker(mock_db)


@pytest.fixture
def fresh_fundamentals():
    """Create fresh fundamental data."""
    return {
        'pe_ratio': 25.0,
        'pb_ratio': 3.0,
        'fcf_yield': 4.0,
        'debt_equity': 60.0,
        'current_price': 150.0,
        'market_cap': 1000000000,
        'dividend_yield': 2.0,
        'date': (datetime.now() - timedelta(days=1)).isoformat()
    }


@pytest.fixture
def stale_fundamentals():
    """Create stale fundamental data."""
    return {
        'pe_ratio': 25.0,
        'pb_ratio': 3.0,
        'fcf_yield': 4.0,
        'debt_equity': 60.0,
        'current_price': 150.0,
        'market_cap': 1000000000,
        'dividend_yield': 2.0,
        'date': (datetime.now() - timedelta(days=10)).isoformat()
    }


@pytest.fixture
def fresh_price_history():
    """Create fresh price history."""
    dates = pd.date_range(end=datetime.now() - timedelta(days=1), periods=250)
    return pd.DataFrame({
        'date': dates,
        'open': 100.0,
        'high': 105.0,
        'low': 95.0,
        'close': 100.0,
        'volume': 1000000.0
    })


@pytest.fixture
def stale_price_history():
    """Create stale price history."""
    dates = pd.date_range(end=datetime.now() - timedelta(days=5), periods=250)
    return pd.DataFrame({
        'date': dates,
        'open': 100.0,
        'high': 105.0,
        'low': 95.0,
        'close': 100.0,
        'volume': 1000000.0
    })


class TestDataQualityIssue:
    """Test DataQualityIssue class."""

    def test_issue_creation(self):
        """Test creating a data quality issue."""
        issue = DataQualityIssue(
            ticker="AAPL",
            issue_type="stale_data",
            severity=IssueSeverity.WARNING,
            description="Data is 10 days old"
        )

        assert issue.ticker == "AAPL"
        assert issue.issue_type == "stale_data"
        assert issue.severity == IssueSeverity.WARNING
        assert issue.description == "Data is 10 days old"
        assert isinstance(issue.detected_at, datetime)

    def test_issue_string_representation(self):
        """Test issue string representation."""
        issue = DataQualityIssue(
            ticker="AAPL",
            issue_type="test",
            severity=IssueSeverity.CRITICAL,
            description="Test issue"
        )

        str_repr = str(issue)
        assert "AAPL" in str_repr
        assert "CRITICAL" in str_repr
        assert "Test issue" in str_repr


class TestTickerQualityReport:
    """Test TickerQualityReport class."""

    def test_report_creation(self):
        """Test creating a quality report."""
        report = TickerQualityReport(ticker="AAPL")

        assert report.ticker == "AAPL"
        assert report.overall_score == 0.0
        assert report.issues == []
        assert report.has_critical_issues is False
        assert report.needs_refresh is False

    def test_add_issue(self):
        """Test adding issues to report."""
        report = TickerQualityReport(ticker="AAPL")

        warning_issue = DataQualityIssue(
            ticker="AAPL",
            issue_type="warning",
            severity=IssueSeverity.WARNING,
            description="Warning"
        )
        report.add_issue(warning_issue)

        assert len(report.issues) == 1
        assert report.has_critical_issues is False

        critical_issue = DataQualityIssue(
            ticker="AAPL",
            issue_type="critical",
            severity=IssueSeverity.CRITICAL,
            description="Critical"
        )
        report.add_issue(critical_issue)

        assert len(report.issues) == 2
        assert report.has_critical_issues is True

    def test_get_issues_by_severity(self):
        """Test filtering issues by severity."""
        report = TickerQualityReport(ticker="AAPL")

        report.add_issue(DataQualityIssue(
            ticker="AAPL", issue_type="c1", severity=IssueSeverity.CRITICAL, description="C1"
        ))
        report.add_issue(DataQualityIssue(
            ticker="AAPL", issue_type="w1", severity=IssueSeverity.WARNING, description="W1"
        ))
        report.add_issue(DataQualityIssue(
            ticker="AAPL", issue_type="c2", severity=IssueSeverity.CRITICAL, description="C2"
        ))

        critical = [i for i in report.issues if i.severity == IssueSeverity.CRITICAL]
        warnings = [i for i in report.issues if i.severity == IssueSeverity.WARNING]

        assert len(critical) == 2
        assert len(warnings) == 1


class TestFreshnessChecks:
    """Test data freshness validation."""

    def test_fresh_fundamentals(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test that fresh fundamentals pass validation."""
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should not have stale data issues
        stale_issues = [i for i in report.issues if 'stale' in i.issue_type]
        assert len(stale_issues) == 0

    def test_stale_fundamentals(self, quality_checker, stale_fundamentals, fresh_price_history):
        """Test that stale fundamentals are flagged."""
        quality_checker.db.get_latest_fundamentals.return_value = stale_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have stale fundamentals issue
        stale_issues = [i for i in report.issues if i.issue_type == 'stale_fundamentals']
        assert len(stale_issues) == 1
        assert stale_issues[0].severity == IssueSeverity.WARNING

    def test_stale_prices(self, quality_checker, fresh_fundamentals, stale_price_history):
        """Test that stale prices are flagged."""
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = stale_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have stale prices issue
        stale_issues = [i for i in report.issues if i.issue_type == 'stale_prices']
        assert len(stale_issues) == 1
        assert stale_issues[0].severity == IssueSeverity.WARNING

    def test_missing_prices(self, quality_checker, fresh_fundamentals):
        """Test that missing price history is flagged."""
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = pd.DataFrame()

        report = quality_checker.check_ticker("AAPL")

        # Should have missing prices issue
        missing_issues = [i for i in report.issues if i.issue_type == 'missing_prices']
        assert len(missing_issues) == 1
        assert missing_issues[0].severity == IssueSeverity.CRITICAL


class TestCompletenessChecks:
    """Test data completeness validation."""

    def test_complete_fundamentals(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test that complete fundamentals pass validation."""
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have high completeness score
        assert report.fundamental_completeness >= 80.0

    def test_missing_required_fields(self, quality_checker, fresh_price_history):
        """Test that missing required fields are flagged."""
        incomplete_fundamentals = {
            'pe_ratio': None,  # Missing required field
            'pb_ratio': 3.0,
            'current_price': 150.0,
            'date': datetime.now().isoformat()
        }
        quality_checker.db.get_latest_fundamentals.return_value = incomplete_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have missing required fields issue
        missing_issues = [i for i in report.issues if i.issue_type == 'missing_required_fields']
        assert len(missing_issues) == 1
        assert missing_issues[0].severity == IssueSeverity.CRITICAL

    def test_missing_optional_fields(self, quality_checker, fresh_price_history):
        """Test that missing optional fields are flagged as info."""
        incomplete_fundamentals = {
            'pe_ratio': 25.0,
            'pb_ratio': 3.0,
            'current_price': 150.0,
            'fcf_yield': None,  # Missing optional field
            'date': datetime.now().isoformat()
        }
        quality_checker.db.get_latest_fundamentals.return_value = incomplete_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have missing optional fields issue
        missing_issues = [i for i in report.issues if i.issue_type == 'missing_optional_fields']
        assert len(missing_issues) == 1
        assert missing_issues[0].severity == IssueSeverity.INFO

    def test_insufficient_history(self, quality_checker, fresh_fundamentals):
        """Test that insufficient price history is flagged."""
        short_history = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=50),
            'close': 100.0,
            'volume': 1000000.0
        })
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = short_history

        report = quality_checker.check_ticker("AAPL")

        # Should have insufficient history issue
        history_issues = [i for i in report.issues if i.issue_type == 'insufficient_history']
        assert len(history_issues) == 1
        assert history_issues[0].severity == IssueSeverity.WARNING


class TestAnomalyDetection:
    """Test anomaly detection."""

    def test_extreme_pe_ratio(self, quality_checker, fresh_price_history):
        """Test that extreme P/E ratios are flagged."""
        extreme_fundamentals = {
            'pe_ratio': 600.0,  # Extremely high
            'pb_ratio': 3.0,
            'current_price': 150.0,
            'last_updated': datetime.now()
        }
        quality_checker.db.get_latest_fundamentals.return_value = extreme_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have extreme PE issue
        pe_issues = [i for i in report.issues if i.issue_type == 'extreme_pe']
        assert len(pe_issues) == 1
        assert pe_issues[0].severity == IssueSeverity.WARNING

    def test_negative_pe_ratio(self, quality_checker, fresh_price_history):
        """Test that negative P/E ratios are flagged as info."""
        negative_pe_fundamentals = {
            'pe_ratio': -10.0,  # Negative (losses)
            'pb_ratio': 3.0,
            'current_price': 150.0,
            'last_updated': datetime.now()
        }
        quality_checker.db.get_latest_fundamentals.return_value = negative_pe_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have negative PE issue
        pe_issues = [i for i in report.issues if i.issue_type == 'negative_pe']
        assert len(pe_issues) == 1
        assert pe_issues[0].severity == IssueSeverity.INFO

    def test_extreme_pb_ratio(self, quality_checker, fresh_price_history):
        """Test that extreme P/B ratios are flagged."""
        extreme_fundamentals = {
            'pe_ratio': 25.0,
            'pb_ratio': 150.0,  # Extremely high
            'current_price': 150.0,
            'last_updated': datetime.now()
        }
        quality_checker.db.get_latest_fundamentals.return_value = extreme_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have extreme PB issue
        pb_issues = [i for i in report.issues if i.issue_type == 'extreme_pb']
        assert len(pb_issues) == 1
        assert pb_issues[0].severity == IssueSeverity.WARNING

    def test_price_spike_detection(self, quality_checker, fresh_fundamentals):
        """Test that price spikes are detected."""
        # Create price history with a spike
        dates = pd.date_range(end=datetime.now(), periods=100)
        closes = [100.0] * 100
        closes[50] = 150.0  # 50% spike

        spike_history = pd.DataFrame({
            'date': dates,
            'close': closes,
            'volume': 1000000.0
        })

        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = spike_history

        report = quality_checker.check_ticker("AAPL")

        # Should have price spike issue
        spike_issues = [i for i in report.issues if i.issue_type == 'price_spike']
        assert len(spike_issues) == 1
        assert spike_issues[0].severity == IssueSeverity.WARNING

    def test_volume_spike_detection(self, quality_checker, fresh_fundamentals):
        """Test that volume spikes are detected."""
        # Create price history with volume spike
        dates = pd.date_range(end=datetime.now(), periods=100)
        volumes = [1000000.0] * 100
        volumes[50] = 10000000.0  # 10x spike

        volume_spike_history = pd.DataFrame({
            'date': dates,
            'close': 100.0,
            'volume': volumes
        })

        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = volume_spike_history

        report = quality_checker.check_ticker("AAPL")

        # Should have volume spike issue
        volume_issues = [i for i in report.issues if i.issue_type == 'volume_spike']
        assert len(volume_issues) == 1

    def test_zero_volume_detection(self, quality_checker, fresh_fundamentals):
        """Test that zero volume days are detected."""
        # Create price history with zero volume days
        dates = pd.date_range(end=datetime.now(), periods=100)
        volumes = [1000000.0] * 100
        volumes[50] = 0.0  # Zero volume

        zero_volume_history = pd.DataFrame({
            'date': dates,
            'close': 100.0,
            'volume': volumes
        })

        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = zero_volume_history

        report = quality_checker.check_ticker("AAPL")

        # Should have zero volume issue
        zero_vol_issues = [i for i in report.issues if i.issue_type == 'zero_volume']
        assert len(zero_vol_issues) == 1
        assert zero_vol_issues[0].severity == IssueSeverity.WARNING


class TestQualityScoring:
    """Test quality score calculation."""

    def test_perfect_score(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test that perfect data gets high score."""
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have high quality score (>90)
        assert report.overall_score >= 90.0

    def test_score_with_critical_issue(self, quality_checker, fresh_price_history):
        """Test that critical issues significantly lower score."""
        incomplete_fundamentals = {
            'pe_ratio': None,  # Critical: missing required field
            'pb_ratio': None,
            'current_price': None,
            'date': datetime.now().isoformat()
        }
        quality_checker.db.get_latest_fundamentals.return_value = incomplete_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have lower score (30 points deducted per critical issue)
        # Score starts at 100, minus 30 for critical issue, but gets bonuses for history
        assert report.overall_score < 90.0
        assert report.has_critical_issues is True

    def test_score_with_warnings(self, quality_checker, stale_fundamentals, fresh_price_history):
        """Test that warnings moderately lower score."""
        quality_checker.db.get_latest_fundamentals.return_value = stale_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        report = quality_checker.check_ticker("AAPL")

        # Should have moderately high score (warnings deduct 10 points but bonuses may offset)
        assert report.overall_score >= 70.0
        assert len([i for i in report.issues if i.severity.value == "warning"]) > 0


class TestCheckAllTickers:
    """Test checking multiple tickers."""

    def test_check_all_tickers(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test checking all tickers in database."""
        quality_checker.db.get_all_tickers.return_value = ["AAPL", "MSFT", "GOOGL"]
        quality_checker.db.get_latest_fundamentals.return_value = fresh_fundamentals
        quality_checker.db.get_price_history.return_value = fresh_price_history

        reports = quality_checker.check_all_tickers()

        assert len(reports) == 3
        assert "AAPL" in reports
        assert "MSFT" in reports
        assert "GOOGL" in reports

    def test_check_all_with_error(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test that errors are handled gracefully."""
        quality_checker.db.get_all_tickers.return_value = ["AAPL", "ERROR"]

        def side_effect(ticker):
            if ticker == "ERROR":
                raise Exception("Database error")
            return fresh_fundamentals

        quality_checker.db.get_latest_fundamentals.side_effect = side_effect
        quality_checker.db.get_price_history.return_value = fresh_price_history

        reports = quality_checker.check_all_tickers()

        assert len(reports) == 2
        assert "AAPL" in reports
        assert "ERROR" in reports
        # Error ticker should have critical issue
        assert reports["ERROR"].has_critical_issues is True


class TestReportGeneration:
    """Test report generation."""

    def test_generate_summary_report(self, quality_checker, fresh_fundamentals, fresh_price_history):
        """Test generating summary report."""
        reports = {
            "AAPL": TickerQualityReport(ticker="AAPL", overall_score=95.0),
            "MSFT": TickerQualityReport(ticker="MSFT", overall_score=85.0),
            "FAIL": TickerQualityReport(ticker="FAIL", overall_score=30.0)
        }
        reports["FAIL"].needs_refresh = True

        summary = quality_checker.generate_summary_report(reports)

        assert "DATA QUALITY SUMMARY REPORT" in summary
        assert "AAPL" in summary
        assert "MSFT" in summary
        assert "FAIL" in summary
        assert "Average Quality Score" in summary
        assert "Tickers Needing Refresh" in summary

    def test_report_categorization(self, quality_checker):
        """Test that tickers are categorized by quality."""
        reports = {
            "EXCELLENT": TickerQualityReport(ticker="EXCELLENT", overall_score=95.0),
            "GOOD": TickerQualityReport(ticker="GOOD", overall_score=80.0),
            "FAIR": TickerQualityReport(ticker="FAIR", overall_score=60.0),
            "POOR": TickerQualityReport(ticker="POOR", overall_score=30.0)
        }

        summary = quality_checker.generate_summary_report(reports)

        assert "Excellent (90-100)" in summary
        assert "Good (70-89)" in summary
        assert "Fair (50-69)" in summary
        assert "Poor (0-49)" in summary


class TestMissingFundamentals:
    """Test handling of missing fundamental data."""

    def test_missing_fundamentals_critical(self, quality_checker):
        """Test that missing fundamentals is critical."""
        quality_checker.db.get_latest_fundamentals.return_value = None
        quality_checker.db.get_price_history.return_value = pd.DataFrame()

        report = quality_checker.check_ticker("AAPL")

        assert report.overall_score == 0.0
        assert report.has_critical_issues is True
        assert report.needs_refresh is True
        missing_issues = [i for i in report.issues if i.issue_type == 'missing_fundamentals']
        assert len(missing_issues) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
