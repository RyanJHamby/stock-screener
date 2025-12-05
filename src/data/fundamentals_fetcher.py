"""Enhanced fundamentals fetcher for quarterly financial data.

This module fetches detailed quarterly financial metrics including:
- Quarterly sales and EPS
- YoY and sequential % changes
- Inventory levels and breakdown
- Margin analysis
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

import yfinance as yf
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_quarterly_financials(ticker: str) -> Dict[str, any]:
    """Fetch quarterly financial data for a stock.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with quarterly financial metrics
    """
    try:
        stock = yf.Ticker(ticker)

        # Get quarterly financials
        quarterly_income = stock.quarterly_financials
        quarterly_balance = stock.quarterly_balance_sheet
        quarterly_cashflow = stock.quarterly_cashflow

        if quarterly_income.empty:
            logger.warning(f"No quarterly income data for {ticker}")
            return {}

        result = {
            'ticker': ticker,
            'fetch_date': datetime.now().isoformat()
        }

        # Get quarterly revenue (Total Revenue)
        if 'Total Revenue' in quarterly_income.index:
            revenues = quarterly_income.loc['Total Revenue'].sort_index()
            result['quarterly_revenue'] = revenues.to_dict()

            if len(revenues) >= 2:
                latest_rev = revenues.iloc[-1]
                prev_rev = revenues.iloc[-2]
                result['revenue_qoq_change'] = ((latest_rev - prev_rev) / prev_rev * 100) if prev_rev != 0 else 0

            if len(revenues) >= 5:
                latest_rev = revenues.iloc[-1]
                yoy_rev = revenues.iloc[-5]
                # Check for NaN or 0 values - treat as missing data
                import math
                if not math.isnan(latest_rev) and not math.isnan(yoy_rev) and yoy_rev != 0 and latest_rev != 0:
                    result['revenue_yoy_change'] = ((latest_rev - yoy_rev) / yoy_rev * 100)
                else:
                    result['revenue_yoy_change'] = None  # Explicitly mark as missing

        # Get quarterly EPS (Basic EPS or Diluted EPS)
        eps_key = None
        if 'Diluted EPS' in quarterly_income.index:
            eps_key = 'Diluted EPS'
        elif 'Basic EPS' in quarterly_income.index:
            eps_key = 'Basic EPS'

        if eps_key:
            eps_values = quarterly_income.loc[eps_key].sort_index()
            result['quarterly_eps'] = eps_values.to_dict()

            if len(eps_values) >= 2:
                latest_eps = eps_values.iloc[-1]
                prev_eps = eps_values.iloc[-2]
                if prev_eps != 0:
                    result['eps_qoq_change'] = ((latest_eps - prev_eps) / abs(prev_eps) * 100)
                else:
                    result['eps_qoq_change'] = 0

            if len(eps_values) >= 5:
                latest_eps = eps_values.iloc[-1]
                yoy_eps = eps_values.iloc[-5]
                import math
                if not math.isnan(latest_eps) and not math.isnan(yoy_eps) and yoy_eps != 0:
                    result['eps_yoy_change'] = ((latest_eps - yoy_eps) / abs(yoy_eps) * 100)
                else:
                    result['eps_yoy_change'] = None  # Explicitly mark as missing

        # Get gross profit margin
        if 'Gross Profit' in quarterly_income.index and 'Total Revenue' in quarterly_income.index:
            gross_profit = quarterly_income.loc['Gross Profit'].sort_index()
            revenue = quarterly_income.loc['Total Revenue'].sort_index()

            if len(gross_profit) > 0 and len(revenue) > 0:
                latest_margin = (gross_profit.iloc[-1] / revenue.iloc[-1] * 100) if revenue.iloc[-1] != 0 else 0
                result['gross_margin'] = round(latest_margin, 2)

                if len(gross_profit) >= 2:
                    prev_margin = (gross_profit.iloc[-2] / revenue.iloc[-2] * 100) if revenue.iloc[-2] != 0 else 0
                    result['margin_change'] = round(latest_margin - prev_margin, 2)

        # Get operating margin
        if 'Operating Income' in quarterly_income.index and 'Total Revenue' in quarterly_income.index:
            operating_income = quarterly_income.loc['Operating Income'].sort_index()
            revenue = quarterly_income.loc['Total Revenue'].sort_index()

            if len(operating_income) > 0 and len(revenue) > 0:
                latest_op_margin = (operating_income.iloc[-1] / revenue.iloc[-1] * 100) if revenue.iloc[-1] != 0 else 0
                result['operating_margin'] = round(latest_op_margin, 2)

        # Get inventory data from balance sheet
        if not quarterly_balance.empty and 'Inventory' in quarterly_balance.index:
            inventory = quarterly_balance.loc['Inventory'].sort_index()
            result['quarterly_inventory'] = inventory.to_dict()

            if len(inventory) >= 2:
                latest_inv = inventory.iloc[-1]
                prev_inv = inventory.iloc[-2]
                import math
                if not math.isnan(latest_inv) and not math.isnan(prev_inv) and prev_inv != 0 and latest_inv != 0:
                    inv_change = ((latest_inv - prev_inv) / prev_inv * 100)
                    result['inventory_qoq_change'] = round(inv_change, 2)
                else:
                    result['inventory_qoq_change'] = None  # Explicitly mark as missing

            # Calculate inventory to sales ratio
            if 'Total Revenue' in quarterly_income.index:
                revenues = quarterly_income.loc['Total Revenue'].sort_index()
                if len(revenues) > 0:
                    latest_inv = inventory.iloc[-1]
                    latest_rev = revenues.iloc[-1]
                    inv_to_sales = (latest_inv / latest_rev) if latest_rev != 0 else 0
                    result['inventory_to_sales_ratio'] = round(inv_to_sales, 3)

        # Try to get inventory breakdown (not always available in yfinance)
        # This is a limitation - detailed inventory breakdown often requires premium data
        result['inventory_breakdown_available'] = False

        return result

    except Exception as e:
        logger.error(f"Error fetching quarterly financials for {ticker}: {e}")
        return {}


def create_fundamental_snapshot(ticker: str, quarterly_data: Dict) -> str:
    """Create a concise fundamental snapshot summary.

    Args:
        ticker: Stock ticker
        quarterly_data: Quarterly financial data

    Returns:
        Formatted snapshot string
    """
    if not quarterly_data:
        return f"FUNDAMENTAL SNAPSHOT - {ticker}\nNo data available"

    snapshot = f"\n{'='*60}\n"
    snapshot += f"FUNDAMENTAL SNAPSHOT - {ticker}\n"
    snapshot += f"{'='*60}\n"

    # Revenue analysis
    yoy = quarterly_data.get('revenue_yoy_change')
    qoq = quarterly_data.get('revenue_qoq_change', 0)

    if yoy is not None:
        if yoy > 20:
            snapshot += f"✓ Revenue: ACCELERATING strongly (YoY: +{yoy:.1f}%, QoQ: +{qoq:.1f}%)\n"
        elif yoy > 10:
            snapshot += f"✓ Revenue: Growing well (YoY: +{yoy:.1f}%, QoQ: +{qoq:.1f}%)\n"
        elif yoy > 0:
            snapshot += f"• Revenue: Modest growth (YoY: +{yoy:.1f}%, QoQ: +{qoq:.1f}%)\n"
        else:
            snapshot += f"✗ Revenue: DETERIORATING (YoY: {yoy:.1f}%, QoQ: {qoq:.1f}%)\n"
    else:
        snapshot += "• Revenue: Data not available\n"

    # EPS analysis
    eps_yoy = quarterly_data.get('eps_yoy_change')
    eps_qoq = quarterly_data.get('eps_qoq_change', 0)

    if eps_yoy is not None:
        if eps_yoy > 25:
            snapshot += f"✓ EPS: STRONG growth (YoY: +{eps_yoy:.1f}%, QoQ: +{eps_qoq:.1f}%)\n"
        elif eps_yoy > 10:
            snapshot += f"✓ EPS: Growing (YoY: +{eps_yoy:.1f}%, QoQ: +{eps_qoq:.1f}%)\n"
        elif eps_yoy > 0:
            snapshot += f"• EPS: Slight growth (YoY: +{eps_yoy:.1f}%, QoQ: +{eps_qoq:.1f}%)\n"
        else:
            snapshot += f"✗ EPS: DECLINING (YoY: {eps_yoy:.1f}%, QoQ: {eps_qoq:.1f}%)\n"
    else:
        snapshot += "• EPS: Data not available\n"

    # Margin analysis
    if 'gross_margin' in quarterly_data:
        margin = quarterly_data['gross_margin']
        margin_change = quarterly_data.get('margin_change', 0)

        if margin_change > 1:
            snapshot += f"✓ Margins: EXPANDING ({margin:.1f}%, +{margin_change:.1f}pp QoQ)\n"
        elif margin_change > 0:
            snapshot += f"• Margins: Stable/slightly up ({margin:.1f}%, +{margin_change:.1f}pp QoQ)\n"
        elif margin_change > -1:
            snapshot += f"• Margins: Flat ({margin:.1f}%, {margin_change:.1f}pp QoQ)\n"
        else:
            snapshot += f"✗ Margins: CONTRACTING ({margin:.1f}%, {margin_change:.1f}pp QoQ)\n"

    # Inventory analysis
    inv_change = quarterly_data.get('inventory_qoq_change')
    inv_to_sales = quarterly_data.get('inventory_to_sales_ratio', 0)

    if inv_change is not None:
        if inv_change > 10:
            snapshot += f"⚠ Inventory: BUILDING (+{inv_change:.1f}% QoQ, ratio: {inv_to_sales:.2f})\n"
            snapshot += "  → Potential demand weakness or production ramp\n"
        elif inv_change > 5:
            snapshot += f"• Inventory: Moderate build (+{inv_change:.1f}% QoQ, ratio: {inv_to_sales:.2f})\n"
        elif inv_change > 0:
            snapshot += f"• Inventory: Slight increase (+{inv_change:.1f}% QoQ, ratio: {inv_to_sales:.2f})\n"
        elif inv_change > -5:
            snapshot += f"• Inventory: Slight draw ({inv_change:.1f}% QoQ, ratio: {inv_to_sales:.2f})\n"
        else:
            snapshot += f"✓ Inventory: DRAWING ({inv_change:.1f}% QoQ, ratio: {inv_to_sales:.2f})\n"
            snapshot += "  → Strong demand signal\n"
    # Don't show anything if inventory data missing - many companies don't track inventory

        if not quarterly_data.get('inventory_breakdown_available', False):
            snapshot += "  Note: Detailed breakdown (raw/WIP/finished) not available via API\n"

    # Overall assessment
    snapshot += "\n"
    snapshot += "Overall Assessment:\n"

    # Determine if fundamentals support technical breakout
    supports_breakout = True
    concerns = []

    if quarterly_data.get('revenue_yoy_change', 0) < 0:
        supports_breakout = False
        concerns.append('revenue declining')

    if quarterly_data.get('eps_yoy_change', 0) < 0:
        supports_breakout = False
        concerns.append('EPS declining')

    if quarterly_data.get('margin_change', 0) < -2:
        concerns.append('margins contracting')

    if quarterly_data.get('inventory_qoq_change', 0) > 15:
        concerns.append('inventory building rapidly')

    if supports_breakout and len(concerns) == 0:
        snapshot += "✓ Fundamentals SUPPORT technical breakout\n"
    elif len(concerns) > 0:
        snapshot += f"⚠ Some concerns: {', '.join(concerns)}\n"
        if not supports_breakout:
            snapshot += "✗ Fundamentals CONTRADICT technical breakout\n"

    return snapshot


def analyze_fundamentals_for_signal(quarterly_data: Dict) -> Dict[str, any]:
    """Analyze fundamentals and return structured assessment.

    Args:
        quarterly_data: Quarterly financial data

    Returns:
        Dict with assessment and flags
    """
    if not quarterly_data:
        return {
            'revenue_trend': 'unknown',
            'eps_trend': 'unknown',
            'inventory_signal': 'unknown',
            'supports_breakout': False,
            'penalty_points': 10
        }

    revenue_yoy = quarterly_data.get('revenue_yoy_change', 0)
    eps_yoy = quarterly_data.get('eps_yoy_change', 0)
    inv_change = quarterly_data.get('inventory_qoq_change', 0)

    # Assess trends
    if revenue_yoy > 10:
        revenue_trend = 'accelerating'
    elif revenue_yoy > 0:
        revenue_trend = 'growing'
    elif revenue_yoy > -5:
        revenue_trend = 'flat'
    else:
        revenue_trend = 'deteriorating'

    if eps_yoy > 10:
        eps_trend = 'accelerating'
    elif eps_yoy > 0:
        eps_trend = 'growing'
    elif eps_yoy > -5:
        eps_trend = 'flat'
    else:
        eps_trend = 'deteriorating'

    if inv_change > 15:
        inventory_signal = 'negative'
    elif inv_change > 5:
        inventory_signal = 'caution'
    else:
        inventory_signal = 'neutral'

    # Determine if fundamentals support breakout
    supports_breakout = (
        revenue_trend in ['accelerating', 'growing'] and
        eps_trend in ['accelerating', 'growing'] and
        inventory_signal != 'negative'
    )

    # Calculate penalty
    penalty = 0
    if revenue_trend == 'deteriorating':
        penalty += 5
    if eps_trend == 'deteriorating':
        penalty += 5
    if inventory_signal == 'negative':
        penalty += 5

    return {
        'revenue_trend': revenue_trend,
        'eps_trend': eps_trend,
        'inventory_signal': inventory_signal,
        'supports_breakout': supports_breakout,
        'penalty_points': penalty
    }
