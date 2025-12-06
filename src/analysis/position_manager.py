#!/usr/bin/env python3
"""Position management and stop loss recommendations.

Analyzes current Robinhood positions and recommends:
- When to move stop loss up (trail stops)
- New stop loss levels with rationale
- When to take partial profits
- Exit target adjustments

Only provides recommendations for SHORT-TERM positions (held <1 year).
Long-term positions (held 1+ years) are excluded to preserve favorable tax treatment.

Uses cached price data from daily scans - no additional API calls needed.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import yfinance as yf
import pandas as pd

from src.screening.phase_indicators import classify_phase
from src.data.git_storage_fetcher import GitStorageFetcher

logger = logging.getLogger(__name__)


class PositionManager:
    """Analyze positions and recommend stop loss adjustments.

    Uses cached fundamentals and price data to avoid extra API calls.
    """

    def __init__(self, use_cache: bool = True):
        """Initialize position manager.

        Args:
            use_cache: Use cached fundamentals and price data (recommended)
        """
        self.use_cache = use_cache
        self.git_fetcher = GitStorageFetcher() if use_cache else None
        self.fundamentals_dir = Path("./data/fundamentals_cache")

    def _get_price_data(self, ticker: str) -> pd.DataFrame:
        """Get price data from cache or yfinance.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with price data
        """
        if self.use_cache and self.git_fetcher:
            try:
                # Try to get cached data first
                price_data = self.git_fetcher.fetch_price_fresh(ticker)
                if not price_data.empty:
                    logger.debug(f"{ticker}: Using cached price data")
                    return price_data
            except Exception as e:
                logger.debug(f"{ticker}: Cache fetch failed, falling back to yfinance: {e}")

        # Fallback to yfinance
        try:
            stock = yf.Ticker(ticker)
            price_data = stock.history(period='1y', interval='1d')
            if not price_data.empty:
                logger.debug(f"{ticker}: Fetched fresh price data from yfinance")
            return price_data
        except Exception as e:
            logger.error(f"{ticker}: Failed to fetch price data: {e}")
            return pd.DataFrame()

    def _get_cached_fundamentals(self, ticker: str) -> Dict:
        """Get cached fundamentals if available.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with fundamental data, or empty dict if not cached
        """
        if not self.use_cache:
            return {}

        try:
            fundamental_file = self.fundamentals_dir / f"{ticker}_fundamentals.json"
            if fundamental_file.exists():
                with open(fundamental_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"{ticker}: Loaded cached fundamentals")
                    return data.get('data', {})
        except Exception as e:
            logger.debug(f"{ticker}: Could not load cached fundamentals: {e}")

        return {}

    def analyze_position(
        self,
        ticker: str,
        entry_price: float,
        current_price: float,
        entry_date: Optional[datetime] = None
    ) -> Dict:
        """Analyze a single position and recommend stop management.

        Args:
            ticker: Stock symbol
            entry_price: Your average entry price
            current_price: Current market price
            entry_date: When you entered (optional, for tax treatment check)

        Returns:
            Dict with recommendations:
            - should_adjust_stop: bool
            - recommended_stop: float (new stop level)
            - current_gain_pct: float
            - rationale: str (why adjust)
            - action: str (trail_to_breakeven, trail_to_profit, take_partial, hold)
            - tax_treatment: str (short_term or long_term)
        """
        result = {
            'ticker': ticker,
            'entry_price': entry_price,
            'current_price': current_price,
            'should_adjust_stop': False,
            'recommended_stop': None,
            'current_gain_pct': 0,
            'rationale': '',
            'action': 'hold',
            'tax_treatment': 'unknown',
            'warnings': []
        }

        # Validate prices
        if entry_price <= 0:
            result['warnings'].append('Invalid entry price (zero or negative) - cannot analyze')
            result['rationale'] = f"Cannot analyze - invalid entry price: ${entry_price:.2f}"
            return result

        if current_price <= 0:
            result['warnings'].append('Invalid current price (zero or negative) - cannot analyze')
            result['rationale'] = f"Cannot analyze - invalid current price: ${current_price:.2f}"
            return result

        # Calculate current gain
        gain_pct = ((current_price - entry_price) / entry_price) * 100
        result['current_gain_pct'] = round(gain_pct, 2)

        # Check tax treatment
        if entry_date:
            days_held = (datetime.now() - entry_date).days
            if days_held >= 365:
                result['tax_treatment'] = 'long_term'
                result['rationale'] = f"LONG-TERM HOLD ({days_held} days) - Preserve long-term capital gains tax rate. No stop adjustment recommended."
                return result
            else:
                result['tax_treatment'] = 'short_term'
                result['days_held'] = days_held

        # Fetch price data and analyze (uses cache by default)
        try:
            price_data = self._get_price_data(ticker)

            if price_data.empty or len(price_data) < 50:
                result['warnings'].append('Insufficient price data for analysis')
                return result

            # Calculate phase and technical levels
            phase_info = classify_phase(price_data, current_price)
            phase = phase_info['phase']

            sma_50 = phase_info.get('sma_50', 0)
            sma_200 = phase_info.get('sma_200', 0)

            # Recent swing low (last 10 days)
            recent_low = price_data['Low'].iloc[-10:].min()

            result['phase'] = phase
            result['sma_50'] = round(sma_50, 2)
            result['recent_low'] = round(recent_low, 2)

            # STOP LOSS ADJUSTMENT LOGIC - LINEAR FORMULAS (NO BUCKETS)
            # Based on continuous gain percentage scaling

            if gain_pct < 5:
                # Small gain - don't adjust yet
                result['action'] = 'hold'
                result['rationale'] = f"Position up {gain_pct:.1f}% - hold initial stop. Wait for 5%+ gain before adjusting."

            else:
                # Gains of 5%+ trigger stop adjustments
                result['should_adjust_stop'] = True

                # CALCULATE PROFIT-BASED STOP (scales linearly with gain)
                # Formula: entry * (1 + min(gain_pct - 3, gain_pct * 0.5) / 100)
                # - At 5% gain → lock in ~1% profit (entry * 1.01)
                # - At 10% gain → lock in ~3.5% profit (entry * 1.035)
                # - At 20% gain → lock in ~8.5% profit (entry * 1.085)
                # - At 40% gain → lock in ~18.5% profit (entry * 1.185)
                # This scales smoothly - bigger gains = more profit locked in

                locked_profit_pct = min(gain_pct - 3, gain_pct * 0.5)
                profit_based_stop = entry_price * (1 + locked_profit_pct / 100)

                # CALCULATE SMA-BASED STOP (if applicable)
                sma_based_stop = None
                if sma_50 > 0 and sma_50 < current_price:
                    # Distance below 50 SMA scales with gain size
                    # Small gains (5-15%) → 1% below SMA
                    # Medium gains (15-30%) → 0.7% below SMA
                    # Large gains (30%+) → 0.5% below SMA
                    sma_buffer_pct = max(0.5, 1.5 - (gain_pct / 50))  # Linear from 1.5% to 0.5%
                    sma_based_stop = sma_50 * (1 - sma_buffer_pct / 100)

                # USE WHICHEVER STOP IS HIGHER (more conservative)
                if sma_based_stop and sma_based_stop > profit_based_stop:
                    result['recommended_stop'] = round(sma_based_stop, 2)
                    stop_type = "SMA-based"
                    sma_buffer_pct = ((sma_50 - result['recommended_stop']) / sma_50) * 100
                else:
                    result['recommended_stop'] = round(profit_based_stop, 2)
                    stop_type = "profit-based"

                # Calculate what % profit is locked in
                locked_profit = ((result['recommended_stop'] / entry_price) - 1) * 100

                # DETERMINE ACTION AND PARTIAL EXIT % (scales linearly)
                # Formula for partial exit: min(50, max(0, (gain_pct - 15) * 2.5))
                # - 0-15% gain → No partial exit (0%)
                # - 20% gain → 12.5% partial exit
                # - 25% gain → 25% partial exit
                # - 30% gain → 37.5% partial exit
                # - 35% gain → 50% partial exit (capped)
                partial_exit_pct = min(50, max(0, (gain_pct - 15) * 2.5))

                if partial_exit_pct > 35:
                    result['action'] = 'take_major_partial_and_trail_tight'
                    action_desc = f"SELL {partial_exit_pct:.0f}%"
                elif partial_exit_pct > 10:
                    result['action'] = 'take_partial_and_trail'
                    action_desc = f"CONSIDER SELLING {partial_exit_pct:.0f}%"
                elif gain_pct >= 10:
                    result['action'] = 'trail_to_profit'
                    action_desc = "TRAIL TO PROFIT"
                else:
                    result['action'] = 'trail_to_breakeven'
                    action_desc = "TRAIL TO BREAKEVEN"

                # BUILD RATIONALE
                rationale_lines = []
                rationale_lines.append(f"Position up {gain_pct:.1f}% - {action_desc}")
                rationale_lines.append("")

                if partial_exit_pct > 0:
                    remaining_pct = 100 - partial_exit_pct
                    rationale_lines.append(f"  RECOMMENDED ACTION:")
                    rationale_lines.append(f"    • Sell {partial_exit_pct:.0f}% at ${current_price:.2f} (lock in ${(current_price - entry_price) * partial_exit_pct / 100:.2f}/share)")
                    rationale_lines.append(f"    • Trail remaining {remaining_pct:.0f}% with stop at ${result['recommended_stop']:.2f}")
                    rationale_lines.append(f"    • Effective: locks minimum +{locked_profit:.1f}% on full position")
                else:
                    rationale_lines.append(f"  NEW STOP LOSS: ${result['recommended_stop']:.2f}")
                    rationale_lines.append(f"    • Locks in minimum +{locked_profit:.1f}% profit")
                    rationale_lines.append(f"    • Stop type: {stop_type}")

                rationale_lines.append("")
                rationale_lines.append(f"  Technical: Phase {phase} | 50 SMA: ${sma_50:.2f}")

                # Add Phase 3 warning for big winners
                if phase == 3 and gain_pct >= 20:
                    rationale_lines.append(f"  ⚠️ WARNING: Stock in Phase 3 (distribution). Consider tighter exit.")

                result['rationale'] = "\n".join(rationale_lines)
                result['partial_exit_pct'] = round(partial_exit_pct, 1)
                result['locked_profit_pct'] = round(locked_profit, 2)

            # Additional checks
            if phase == 3 or phase == 4:
                result['warnings'].append(
                    f'⚠️ Stock in Phase {phase} (distribution/decline). Consider tighter stops or exit.'
                )

            if current_price < sma_50 and sma_50 > 0:
                result['warnings'].append(
                    f'⚠️ Price broke below 50 SMA (${sma_50:.2f}). Trend weakening - review position.'
                )

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            result['warnings'].append(f'Analysis error: {str(e)}')

        return result

    def analyze_portfolio(
        self,
        positions: List[Dict],
        entry_dates: Optional[Dict[str, datetime]] = None
    ) -> Dict:
        """Analyze all positions and generate comprehensive report.

        Args:
            positions: List of position dicts from RobinhoodPositionFetcher
            entry_dates: Optional dict of {ticker: entry_date} for tax treatment

        Returns:
            Dict with:
            - position_analyses: List of individual position analyses
            - summary: Portfolio-level stats
            - urgent_actions: List of positions needing immediate attention
        """
        if not positions:
            return {
                'position_analyses': [],
                'summary': {'total_positions': 0},
                'urgent_actions': []
            }

        entry_dates = entry_dates or {}
        analyses = []

        for pos in positions:
            ticker = pos['ticker']
            entry_date = entry_dates.get(ticker)

            logger.info(f"Analyzing {ticker}: entry=${pos['average_buy_price']:.2f}, current=${pos['current_price']:.2f}")

            analysis = self.analyze_position(
                ticker=ticker,
                entry_price=pos['average_buy_price'],
                current_price=pos['current_price'],
                entry_date=entry_date
            )

            analysis['quantity'] = pos['quantity']
            analyses.append(analysis)

        # Generate summary
        total_positions = len(analyses)
        positions_to_adjust = sum(1 for a in analyses if a['should_adjust_stop'])
        short_term_positions = sum(
            1 for a in analyses if a['tax_treatment'] == 'short_term'
        )
        long_term_positions = sum(
            1 for a in analyses if a['tax_treatment'] == 'long_term'
        )

        avg_gain = sum(a['current_gain_pct'] for a in analyses) / total_positions if total_positions > 0 else 0

        summary = {
            'total_positions': total_positions,
            'positions_need_adjustment': positions_to_adjust,
            'short_term_positions': short_term_positions,
            'long_term_positions': long_term_positions,
            'average_gain_pct': round(avg_gain, 2)
        }

        # Urgent actions (Phase 3/4 warnings, big winners, breakdowns)
        urgent = []
        for analysis in analyses:
            if analysis['warnings']:
                urgent.append({
                    'ticker': analysis['ticker'],
                    'reason': analysis['warnings'],
                    'current_gain': analysis['current_gain_pct']
                })
            elif analysis.get('action') in ['take_partial_and_trail', 'take_partial_and_trail_tight']:
                urgent.append({
                    'ticker': analysis['ticker'],
                    'reason': 'Big winner - consider taking partial profits',
                    'current_gain': analysis['current_gain_pct']
                })

        return {
            'position_analyses': analyses,
            'summary': summary,
            'urgent_actions': urgent,
            'timestamp': datetime.now()
        }

    def format_portfolio_report(self, analysis_result: Dict) -> str:
        """Format portfolio analysis as readable report.

        Args:
            analysis_result: Output from analyze_portfolio()

        Returns:
            Formatted string report
        """
        lines = []
        lines.append("="*80)
        lines.append("POSITION MANAGEMENT REPORT - STOP LOSS RECOMMENDATIONS")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*80)
        lines.append("")

        summary = analysis_result['summary']
        lines.append("PORTFOLIO SUMMARY")
        lines.append("-"*80)
        lines.append(f"Total Positions: {summary['total_positions']}")
        lines.append(f"Need Stop Adjustment: {summary['positions_need_adjustment']}")
        lines.append(f"Short-term (<1 year): {summary['short_term_positions']}")
        lines.append(f"Long-term (1+ years): {summary['long_term_positions']}")
        lines.append(f"Average Gain: {summary['average_gain_pct']:+.2f}%")
        lines.append("")

        # Urgent actions
        if analysis_result['urgent_actions']:
            lines.append("⚠️  URGENT ACTIONS NEEDED")
            lines.append("-"*80)
            for urgent in analysis_result['urgent_actions']:
                lines.append(f"\n{urgent['ticker']} ({urgent['current_gain']:+.1f}%)")
                if isinstance(urgent['reason'], list):
                    for reason in urgent['reason']:
                        lines.append(f"  • {reason}")
                else:
                    lines.append(f"  • {urgent['reason']}")
            lines.append("\n" + "="*80 + "\n")

        # Individual position analyses
        lines.append("POSITION-BY-POSITION ANALYSIS")
        lines.append("="*80)

        for i, analysis in enumerate(analysis_result['position_analyses'], 1):
            lines.append(f"\n{'#'*80}")
            lines.append(f"POSITION #{i}: {analysis['ticker']}")
            lines.append(f"{'#'*80}")

            lines.append(f"Entry: ${analysis['entry_price']:.2f} | Current: ${analysis['current_price']:.2f} | Gain: {analysis['current_gain_pct']:+.2f}%")

            if analysis['tax_treatment'] != 'unknown':
                lines.append(f"Tax Treatment: {analysis['tax_treatment'].upper()}")
                if 'days_held' in analysis:
                    lines.append(f"Days Held: {analysis['days_held']}")

            lines.append("")
            lines.append(f"ACTION: {analysis['action'].replace('_', ' ').upper()}")
            lines.append("")

            if analysis['should_adjust_stop']:
                lines.append(f"✓ RECOMMENDED STOP LOSS: ${analysis['recommended_stop']:.2f}")
                lines.append("")

            lines.append("RATIONALE:")
            lines.append(analysis['rationale'])

            if analysis.get('phase'):
                tech_line = f"\nTechnical: Phase {analysis['phase']}"
                if analysis.get('sma_50'):
                    tech_line += f" | 50 SMA: ${analysis['sma_50']:.2f}"
                lines.append(tech_line)

            if analysis['warnings']:
                lines.append("\nWARNINGS:")
                for warning in analysis['warnings']:
                    lines.append(f"  {warning}")

            lines.append("")

        lines.append("="*80)
        lines.append("END OF REPORT")
        lines.append("="*80)

        return "\n".join(lines)


def main():
    """Example usage."""
    # Example positions
    positions = [
        {'ticker': 'AAPL', 'quantity': 50, 'average_buy_price': 175.50, 'current_price': 182.30},
        {'ticker': 'MSFT', 'quantity': 25, 'average_buy_price': 380.00, 'current_price': 385.50},
        {'ticker': 'NVDA', 'quantity': 30, 'average_buy_price': 495.00, 'current_price': 545.00},
    ]

    # Example entry dates (for tax treatment)
    entry_dates = {
        'AAPL': datetime.now() - timedelta(days=45),  # 45 days ago (short-term)
        'MSFT': datetime.now() - timedelta(days=400),  # 400 days ago (long-term)
        'NVDA': datetime.now() - timedelta(days=20),   # 20 days ago (short-term)
    }

    manager = PositionManager()
    result = manager.analyze_portfolio(positions, entry_dates)

    print(manager.format_portfolio_report(result))


if __name__ == '__main__':
    main()
