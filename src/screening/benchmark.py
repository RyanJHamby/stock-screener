"""Benchmark and market breadth analysis module.

This module analyzes SPY (market benchmark) and calculates market breadth metrics.
"""

import logging
from typing import Dict, List

import pandas as pd

from .phase_indicators import classify_phase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_spy_trend(spy_price_data: pd.DataFrame, current_spy_price: float) -> Dict[str, any]:
    """Analyze SPY trend using Phase classification.

    Args:
        spy_price_data: SPY OHLCV data
        current_spy_price: Current SPY price

    Returns:
        Dict with SPY trend analysis
    """
    if spy_price_data.empty:
        logger.warning("Empty SPY price data")
        return {
            'phase': 0,
            'phase_name': 'Unknown',
            'trend': 'unknown',
            'error': 'No data'
        }

    # Classify SPY phase
    phase_info = classify_phase(spy_price_data, current_spy_price)

    # Determine overall trend
    phase = phase_info['phase']
    if phase == 1:
        trend = 'Consolidating'
    elif phase == 2:
        trend = 'Bullish'
    elif phase == 3:
        trend = 'Topping'
    elif phase == 4:
        trend = 'Bearish'
    else:
        trend = 'Unknown'

    return {
        'ticker': 'SPY',
        'phase': phase,
        'phase_name': phase_info['phase_name'],
        'trend': trend,
        'confidence': phase_info['confidence'],
        'sma_50': phase_info.get('sma_50'),
        'sma_200': phase_info.get('sma_200'),
        'slope_50': phase_info.get('slope_50'),
        'slope_200': phase_info.get('slope_200'),
        'current_price': current_spy_price,
        'reasons': phase_info.get('reasons', [])
    }


def calculate_market_breadth(phase_results: List[Dict]) -> Dict[str, any]:
    """Calculate market breadth metrics.

    Args:
        phase_results: List of phase classification results for all stocks

    Returns:
        Dict with breadth metrics
    """
    if not phase_results:
        return {
            'total_stocks': 0,
            'phase_1_count': 0,
            'phase_2_count': 0,
            'phase_3_count': 0,
            'phase_4_count': 0,
            'phase_1_pct': 0,
            'phase_2_pct': 0,
            'phase_3_pct': 0,
            'phase_4_pct': 0,
            'breadth_quality': 'unknown'
        }

    total = len(phase_results)

    # Count stocks in each phase
    phase_counts = {1: 0, 2: 0, 3: 0, 4: 0, 0: 0}

    for result in phase_results:
        phase = result.get('phase', 0)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    # Calculate percentages
    phase_1_pct = (phase_counts[1] / total * 100) if total > 0 else 0
    phase_2_pct = (phase_counts[2] / total * 100) if total > 0 else 0
    phase_3_pct = (phase_counts[3] / total * 100) if total > 0 else 0
    phase_4_pct = (phase_counts[4] / total * 100) if total > 0 else 0

    # Determine breadth quality
    if phase_2_pct > 50:
        breadth_quality = 'Excellent'
    elif phase_2_pct > 30:
        breadth_quality = 'Good'
    elif phase_2_pct > 15:
        breadth_quality = 'Fair'
    else:
        breadth_quality = 'Weak'

    return {
        'total_stocks': total,
        'phase_1_count': phase_counts[1],
        'phase_2_count': phase_counts[2],
        'phase_3_count': phase_counts[3],
        'phase_4_count': phase_counts[4],
        'phase_1_pct': round(phase_1_pct, 1),
        'phase_2_pct': round(phase_2_pct, 1),
        'phase_3_pct': round(phase_3_pct, 1),
        'phase_4_pct': round(phase_4_pct, 1),
        'breadth_quality': breadth_quality
    }


def classify_market_regime(spy_analysis: Dict, breadth: Dict) -> str:
    """Classify overall market regime (Risk-On vs Risk-Off).

    Args:
        spy_analysis: SPY trend analysis
        breadth: Market breadth metrics

    Returns:
        Market regime classification
    """
    spy_phase = spy_analysis.get('phase', 0)
    phase_2_pct = breadth.get('phase_2_pct', 0)

    # Strong Risk-On conditions
    if spy_phase == 2 and phase_2_pct > 40:
        return 'RISK-ON (Strong)'

    # Moderate Risk-On
    elif spy_phase == 2 and phase_2_pct > 25:
        return 'RISK-ON (Moderate)'

    # Weak Risk-On / Mixed
    elif spy_phase == 2 or (spy_phase == 1 and phase_2_pct > 30):
        return 'RISK-ON (Weak) / Mixed'

    # Risk-Off conditions
    elif spy_phase == 4 or phase_2_pct < 15:
        return 'RISK-OFF'

    # Transitional / Uncertain
    else:
        return 'TRANSITIONAL / Uncertain'


def format_benchmark_summary(spy_analysis: Dict, breadth: Dict) -> str:
    """Format benchmark summary for output.

    Args:
        spy_analysis: SPY analysis dict
        breadth: Market breadth dict

    Returns:
        Formatted summary string
    """
    regime = classify_market_regime(spy_analysis, breadth)

    summary = f"\n{'='*60}\n"
    summary += "BENCHMARK SUMMARY\n"
    summary += f"{'='*60}\n\n"

    # SPY Analysis
    summary += "SPY Trend Classification:\n"
    summary += f"  Phase: {spy_analysis['phase']} - {spy_analysis['phase_name']}\n"
    summary += f"  Trend: {spy_analysis['trend']}\n"
    summary += f"  Current Price: ${spy_analysis.get('current_price', 0):.2f}\n"
    summary += f"  50 SMA: ${spy_analysis.get('sma_50', 0):.2f} (slope: {spy_analysis.get('slope_50', 0):.4f})\n"
    summary += f"  200 SMA: ${spy_analysis.get('sma_200', 0):.2f} (slope: {spy_analysis.get('slope_200', 0):.4f})\n"
    summary += f"  Confidence: {spy_analysis.get('confidence', 0):.0f}%\n"

    # Market Breadth
    summary += f"\nMarket Breadth (n={breadth['total_stocks']}):\n"
    summary += f"  Phase 1 (Base Building): {breadth['phase_1_count']} stocks ({breadth['phase_1_pct']:.1f}%)\n"
    summary += f"  Phase 2 (Uptrend): {breadth['phase_2_count']} stocks ({breadth['phase_2_pct']:.1f}%)\n"
    summary += f"  Phase 3 (Distribution): {breadth['phase_3_count']} stocks ({breadth['phase_3_pct']:.1f}%)\n"
    summary += f"  Phase 4 (Downtrend): {breadth['phase_4_count']} stocks ({breadth['phase_4_pct']:.1f}%)\n"
    summary += f"  Breadth Quality: {breadth['breadth_quality']}\n"

    # Market Regime
    summary += f"\nMarket Regime: {regime}\n"

    # Interpretation
    summary += "\nInterpretation:\n"
    if 'RISK-ON' in regime:
        summary += "  → Favorable environment for breakout trades\n"
        summary += "  → Focus on Phase 2 breakouts with strong RS\n"
    elif 'RISK-OFF' in regime:
        summary += "  → Defensive environment - raise cash, tighten stops\n"
        summary += "  → Avoid new breakouts, focus on preservation\n"
    else:
        summary += "  → Mixed/transitional market - be selective\n"
        summary += "  → Focus on highest quality setups only\n"

    summary += f"{'='*60}\n"

    return summary


def should_generate_signals(spy_analysis: Dict, breadth: Dict,
                             min_phase2_pct: float = 15.0) -> Dict[str, any]:
    """Determine if market conditions warrant generating buy signals.

    Args:
        spy_analysis: SPY analysis
        breadth: Market breadth
        min_phase2_pct: Minimum Phase 2 percentage for signal generation

    Returns:
        Dict with recommendation
    """
    spy_phase = spy_analysis.get('phase', 0)
    phase_2_pct = breadth.get('phase_2_pct', 0)
    regime = classify_market_regime(spy_analysis, breadth)

    # Determine if we should generate buy signals
    should_buy = False
    reasons = []

    if spy_phase in [2, 1]:
        if phase_2_pct >= min_phase2_pct:
            should_buy = True
            reasons.append(f"Market breadth adequate ({phase_2_pct:.1f}% in Phase 2)")
        else:
            reasons.append(f"Market breadth weak ({phase_2_pct:.1f}% in Phase 2, need {min_phase2_pct}%)")
    else:
        reasons.append(f"SPY in unfavorable phase ({spy_phase})")

    # Sell signals - always generate if applicable
    should_sell = True

    return {
        'should_generate_buys': should_buy,
        'should_generate_sells': should_sell,
        'regime': regime,
        'reasons': reasons,
        'phase_2_pct': phase_2_pct,
        'spy_phase': spy_phase
    }
