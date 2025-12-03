"""Signal detection and scoring engine for buy/sell decisions.

This module implements the buy and sell signal detection based on Phase transitions
and technical/fundamental confluence.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .phase_indicators import (
    calculate_volume_ratio,
    calculate_rs_slope,
    detect_volatility_contraction,
    detect_breakout
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def score_buy_signal(
    ticker: str,
    price_data: pd.DataFrame,
    current_price: float,
    phase_info: Dict,
    rs_series: pd.Series,
    fundamentals: Optional[Dict] = None
) -> Dict[str, any]:
    """Score a buy signal for swing/position trading (NOT day trading).

    Based on Weinstein/O'Neil/Minervini Stage 2 methodology with gradual scoring.

    Scoring Components (0-100):
    - Trend structure/Stage quality: 50 points (NOT binary!)
    - Fundamentals: 30 points (growth, margins, inventory)
    - Volume behavior: 10 points (directional context matters!)
    - Relative strength: 10 points (gradual slope)

    Threshold: >= 60 for signals (NOT 70!)

    Args:
        ticker: Stock ticker
        price_data: OHLCV data
        current_price: Current price
        phase_info: Phase classification
        rs_series: Relative strength series
        fundamentals: Optional fundamental analysis

    Returns:
        Dict with buy signal score and details
    """
    phase = phase_info['phase']

    # Only consider Phase 1 and Phase 2
    if phase not in [1, 2]:
        return {
            'ticker': ticker,
            'is_buy': False,
            'score': 0,
            'reason': f'Wrong phase (Phase {phase})',
            'details': {}
        }

    score = 0
    details = {}
    reasons = []

    # ========================================================================
    # 1. TREND STRUCTURE / STAGE QUALITY (50 points) - GRADUAL, NOT BINARY
    # ========================================================================
    trend_score = 0

    sma_50 = phase_info.get('sma_50', 0)
    sma_200 = phase_info.get('sma_200', 0)
    slope_50 = phase_info.get('slope_50', 0)
    slope_200 = phase_info.get('slope_200', 0)
    distance_50 = phase_info.get('distance_from_50sma', 0)
    distance_200 = phase_info.get('distance_from_200sma', 0)

    # A) Base Stage 2 quality (30 points max) - GRADUAL based on strength
    if phase == 2:
        # Not all Stage 2 stocks are equal! Grade by strength
        stage2_quality = 0

        # How far above SMAs? (15 pts)
        if distance_50 >= 5 and distance_200 >= 10:
            stage2_quality += 15  # Strong uptrend
            reasons.append('Strong Stage 2: well above SMAs')
        elif distance_50 >= 2 and distance_200 >= 5:
            stage2_quality += 12  # Good uptrend
            reasons.append('Good Stage 2: above SMAs')
        elif distance_50 >= 0 and distance_200 >= 0:
            stage2_quality += 8   # Weak Stage 2
            reasons.append('Weak Stage 2: barely above SMAs')
        else:
            stage2_quality += 3   # Very weak
            reasons.append('Very weak Stage 2')

        # SMA slopes - are SMAs rising? (15 pts)
        if slope_50 > 0.05 and slope_200 > 0.03:
            stage2_quality += 15  # Strong rising SMAs
            reasons.append(f'SMAs rising strongly (50:{slope_50:.3f}, 200:{slope_200:.3f})')
        elif slope_50 > 0.02 and slope_200 > 0.01:
            stage2_quality += 10  # Moderate
            reasons.append(f'SMAs rising moderately')
        elif slope_50 > 0 and slope_200 > 0:
            stage2_quality += 5   # Weak
            reasons.append(f'SMAs rising weakly')
        else:
            stage2_quality += 0   # Flat/declining
            reasons.append('Warning: SMAs not rising')

        trend_score += stage2_quality

    elif phase == 1:
        # Stage 1 → Stage 2 transition potential (graded 0-25 points)
        transition_score = 0

        # How close to breaking out? (12 pts)
        if distance_50 >= -2 and distance_50 < 5:
            transition_score += 12  # Near 50 SMA
            reasons.append(f'Near 50 SMA ({distance_50:.1f}% away)')
        elif distance_50 >= -5:
            transition_score += 8
            reasons.append(f'Approaching 50 SMA')
        else:
            transition_score += 3
            reasons.append('Far from 50 SMA')

        # SMA setup - golden cross territory? (13 pts)
        if sma_50 > sma_200 and slope_50 > 0:
            transition_score += 13
            reasons.append('50 SMA > 200 SMA (golden cross)')
        elif sma_50 > sma_200 * 0.98:
            transition_score += 8
            reasons.append('Approaching golden cross')
        else:
            transition_score += 3

        trend_score += transition_score

    # B) Breakout detection (10 points)
    breakout_info = detect_breakout(price_data, current_price, phase_info)
    if breakout_info['is_breakout']:
        trend_score += 10
        reasons.append(f"Breakout: {breakout_info['breakout_type']}")
        details['breakout'] = breakout_info

    # C) Over-extension check (10 points penalty)
    if distance_50 > 30:
        trend_score -= 10
        reasons.append(f'⚠ Over-extended: {distance_50:.1f}% above 50 SMA')
    elif distance_50 > 20:
        trend_score -= 5
        reasons.append(f'Moderately extended above 50 SMA')

    score += min(trend_score, 50)
    details['trend_score'] = min(trend_score, 50)

    # ========================================================================
    # 2. FUNDAMENTALS (30 points) - MOST IMPORTANT FOR POSITION TRADING
    # ========================================================================
    fundamental_score = 0

    if fundamentals:
        # A) Growth trends (15 points)
        revenue_trend = fundamentals.get('revenue_trend', 'unknown')
        eps_trend = fundamentals.get('eps_trend', 'unknown')

        if revenue_trend == 'accelerating' and eps_trend == 'accelerating':
            fundamental_score += 15
            reasons.append('✓ Revenue & EPS accelerating')
        elif revenue_trend == 'accelerating' or eps_trend == 'accelerating':
            fundamental_score += 12
            reasons.append('Revenue or EPS accelerating')
        elif revenue_trend == 'growing' and eps_trend == 'growing':
            fundamental_score += 10
            reasons.append('Revenue & EPS growing')
        elif revenue_trend == 'growing' or eps_trend == 'growing':
            fundamental_score += 7
            reasons.append('Some growth present')
        elif revenue_trend == 'flat' and eps_trend == 'flat':
            fundamental_score += 3
            reasons.append('Growth stalled')
        else:
            fundamental_score += 0
            reasons.append('⚠ Revenue or EPS deteriorating')

        # B) Inventory signal (10 points)
        inventory_signal = fundamentals.get('inventory_signal', 'neutral')
        if inventory_signal == 'neutral' or inventory_signal == 'unknown':
            fundamental_score += 10
            reasons.append('Inventory: neutral')
        elif inventory_signal == 'caution':
            fundamental_score += 5
            reasons.append('⚠ Inventory building moderately')
        else:  # negative
            fundamental_score += 0
            reasons.append('⚠ Inventory building rapidly (demand concern)')

        # C) Profit margins expansion (5 points bonus)
        # TODO: Add when margin data available
        fundamental_score += 5  # Placeholder - assume neutral

        details['fundamental_score'] = fundamental_score
    else:
        # No fundamentals available - neutral score
        fundamental_score = 15  # Half of 30
        reasons.append('No fundamental data available')
        details['fundamental_score'] = fundamental_score

    score += fundamental_score

    # ========================================================================
    # 3. VOLUME BEHAVIOR (10 points) - DIRECTIONAL CONTEXT MATTERS!
    # ========================================================================
    volume_score = 0

    if 'Volume' in price_data.columns and len(price_data) >= 30:
        # Look at last 5 days to understand volume context
        recent_prices = price_data['Close'].iloc[-6:]  # 6 days to get 5 changes
        recent_volume = price_data['Volume'].iloc[-5:]
        avg_volume = price_data['Volume'].iloc[-30:-5].mean()

        # Calculate price change context
        up_days = 0
        down_days = 0
        volume_on_up_days = 0
        volume_on_down_days = 0

        for i in range(1, len(recent_prices)):
            price_change = recent_prices.iloc[i] - recent_prices.iloc[i-1]
            vol = recent_volume.iloc[i-1]

            if price_change > 0:
                up_days += 1
                volume_on_up_days += vol
            else:
                down_days += 1
                volume_on_down_days += vol

        # Average volume on up vs down days
        avg_vol_up = (volume_on_up_days / up_days) if up_days > 0 else 0
        avg_vol_down = (volume_on_down_days / down_days) if down_days > 0 else 0

        # Score based on volume behavior
        if avg_vol_up > avg_vol_down * 1.3:
            # Heavy volume on up days = institutions accumulating
            volume_score = 10
            reasons.append(f'✓ Volume heavier on up days ({avg_vol_up/1e6:.1f}M vs {avg_vol_down/1e6:.1f}M)')
        elif avg_vol_up > avg_vol_down:
            volume_score = 7
            reasons.append('Volume slightly heavier on up days')
        elif avg_vol_down > avg_vol_up * 1.3:
            # Heavy volume on down days = distribution
            volume_score = 0
            reasons.append('⚠ Volume heavier on down days (distribution)')
        else:
            volume_score = 4
            reasons.append('Volume pattern neutral')

        details['avg_vol_up'] = round(avg_vol_up, 0)
        details['avg_vol_down'] = round(avg_vol_down, 0)
        details['volume_score'] = volume_score
    else:
        volume_score = 5  # Neutral if no data
        details['volume_score'] = volume_score

    score += volume_score

    # ========================================================================
    # 4. RELATIVE STRENGTH (10 points) - GRADUAL SLOPE
    # ========================================================================
    rs_score = 0

    if len(rs_series) >= 20:
        # Use 20-day RS slope for swing trading
        rs_slope = calculate_rs_slope(rs_series, 20)

        # Gradual scoring curve
        if rs_slope >= 3.0:
            rs_score = 10
            reasons.append(f'Excellent RS: {rs_slope:.2f} (outperforming SPY)')
        elif rs_slope >= 2.0:
            rs_score = 8
            reasons.append(f'Strong RS: {rs_slope:.2f}')
        elif rs_slope >= 1.0:
            rs_score = 6
            reasons.append(f'Good RS: {rs_slope:.2f}')
        elif rs_slope >= 0.5:
            rs_score = 4
            reasons.append(f'Positive RS: {rs_slope:.2f}')
        elif rs_slope >= 0:
            rs_score = 2
            reasons.append(f'Weak RS: {rs_slope:.2f}')
        else:
            rs_score = 0
            reasons.append(f'⚠ Negative RS: {rs_slope:.2f} (underperforming)')

        details['rs_slope'] = round(rs_slope, 3)
        details['rs_score'] = rs_score
    else:
        rs_score = 5  # Neutral if insufficient data
        details['rs_score'] = rs_score

    score += rs_score

    # Final score
    final_score = max(0, min(score, 100))

    # Determine if this is a valid buy signal (>= 60, not 70!)
    is_buy = final_score >= 60

    return {
        'ticker': ticker,
        'is_buy': is_buy,
        'score': round(final_score, 1),
        'phase': phase,
        'breakout_price': breakout_info.get('breakout_level') if breakout_info['is_breakout'] else None,
        'reasons': reasons,
        'details': details
    }


def score_sell_signal(
    ticker: str,
    price_data: pd.DataFrame,
    current_price: float,
    phase_info: Dict,
    rs_series: pd.Series,
    previous_phase: Optional[int] = None
) -> Dict[str, any]:
    """Score a sell signal based on Phase 2->3/4 transition.

    Scoring Components (0-100):
    - Breakdown structure: 60 points
    - Volume confirmation: 30 points
    - RS weakness: 10 points

    Only output scores >= 60

    Args:
        ticker: Stock ticker
        price_data: OHLCV data
        current_price: Current price
        phase_info: Phase classification
        rs_series: Relative strength series
        previous_phase: Previous phase (for transition detection)

    Returns:
        Dict with sell signal score and details
    """
    phase = phase_info['phase']

    # Only consider Phase 3 and Phase 4, or transitions from Phase 2
    if phase not in [3, 4]:
        return {
            'ticker': ticker,
            'is_sell': False,
            'score': 0,
            'severity': 'none',
            'reason': f'No sell signal (Phase {phase})',
            'details': {}
        }

    score = 0
    details = {}
    reasons = []

    # 1. BREAKDOWN STRUCTURE (60 points)
    breakdown_score = 0

    sma_50 = phase_info.get('sma_50', 0)
    sma_200 = phase_info.get('sma_200', 0)
    slope_50 = phase_info.get('slope_50', 0)

    # Phase transition
    if previous_phase == 2 and phase in [3, 4]:
        breakdown_score += 30
        reasons.append(f'Phase transition: {previous_phase} -> {phase}')
    elif phase == 4:
        breakdown_score += 25
        reasons.append('In Phase 4 (Downtrend)')
    elif phase == 3:
        breakdown_score += 15
        reasons.append('In Phase 3 (Distribution)')

    # Breakdown below 50 SMA
    if current_price < sma_50:
        pct_below = ((sma_50 - current_price) / sma_50) * 100
        if pct_below > 5:
            breakdown_score += 20
            reasons.append(f'Broke below 50 SMA by {pct_below:.1f}%')
        elif pct_below > 2:
            breakdown_score += 15
            reasons.append(f'Below 50 SMA by {pct_below:.1f}%')
        else:
            breakdown_score += 10
            reasons.append(f'Just below 50 SMA ({pct_below:.1f}%)')

        details['breakdown_level'] = round(sma_50, 2)

    # Check if 50 SMA is turning down
    if slope_50 < 0:
        breakdown_score += 10
        reasons.append(f'50 SMA declining (slope: {slope_50:.4f})')

    score += min(breakdown_score, 60)
    details['breakdown_score'] = min(breakdown_score, 60)

    # 2. VOLUME CONFIRMATION (30 points)
    volume_score = 0

    if 'Volume' in price_data.columns and len(price_data) >= 20:
        volume_ratio = calculate_volume_ratio(price_data['Volume'], 20)

        # High volume on breakdown is bearish
        if volume_ratio >= 1.5:
            volume_score = 30
            reasons.append(f'High volume breakdown: {volume_ratio:.1f}x')
        elif volume_ratio >= 1.3:
            volume_score = 20
            reasons.append(f'Elevated volume: {volume_ratio:.1f}x')
        elif volume_ratio >= 1.1:
            volume_score = 10
            reasons.append(f'Moderate volume: {volume_ratio:.1f}x')
        else:
            volume_score = 5
            reasons.append(f'Low volume breakdown: {volume_ratio:.1f}x')

        details['volume_ratio'] = round(volume_ratio, 2)

    score += volume_score
    details['volume_score'] = volume_score

    # 3. RS WEAKNESS (10 points)
    rs_score = 0

    if len(rs_series) >= 15:
        rs_slope = calculate_rs_slope(rs_series, 15)

        if rs_slope < 0:
            if rs_slope < -2.0:
                rs_score = 10
                reasons.append(f'Sharp RS decline: {rs_slope:.2f}')
            elif rs_slope < -1.0:
                rs_score = 7
                reasons.append(f'RS declining: {rs_slope:.2f}')
            else:
                rs_score = 5
                reasons.append(f'Weak RS rollover: {rs_slope:.2f}')
        else:
            rs_score = 0
            reasons.append(f'RS still positive: {rs_slope:.2f}')

        details['rs_slope'] = round(rs_slope, 3)

    score += rs_score
    details['rs_score'] = rs_score

    # Check for failed breakout
    close = price_data['Close']
    if len(close) >= 20:
        recent_high = close.iloc[-20:].max()
        if recent_high > sma_50 and current_price < sma_50:
            score += 10
            reasons.append('Failed breakout - closed back inside base')

    # Final score
    final_score = max(0, min(score, 100))

    # Determine severity
    if final_score >= 80:
        severity = 'critical'
    elif final_score >= 70:
        severity = 'high'
    elif final_score >= 60:
        severity = 'medium'
    else:
        severity = 'low'

    # Determine if this is a valid sell signal (>= 60)
    is_sell = final_score >= 60

    return {
        'ticker': ticker,
        'is_sell': is_sell,
        'score': round(final_score, 1),
        'severity': severity,
        'phase': phase,
        'breakdown_level': details.get('breakdown_level'),
        'reasons': reasons,
        'details': details
    }


def format_signal_output(signal: Dict, signal_type: str = 'buy') -> str:
    """Format signal for human-readable output.

    Args:
        signal: Signal dict from score_buy_signal or score_sell_signal
        signal_type: 'buy' or 'sell'

    Returns:
        Formatted string
    """
    ticker = signal['ticker']
    score = signal['score']
    phase = signal['phase']

    if signal_type == 'buy':
        output = f"\n{'='*60}\n"
        output += f"BUY SIGNAL: {ticker} | Score: {score}/100 | Phase {phase}\n"
        output += f"{'='*60}\n"

        if 'breakout_price' in signal and signal['breakout_price']:
            output += f"Breakout Level: ${signal['breakout_price']:.2f}\n"

        details = signal.get('details', {})
        if 'rs_slope' in details:
            output += f"RS Slope: {details['rs_slope']:.3f}\n"
        if 'volume_ratio' in details:
            output += f"Volume vs Avg: {details['volume_ratio']:.1f}x\n"
        if 'distance_from_50sma' in details:
            output += f"Distance from 50 SMA: {details['distance_from_50sma']:.1f}%\n"

        output += f"\nReasons:\n"
        for reason in signal['reasons']:
            output += f"  • {reason}\n"

    else:  # sell
        severity = signal.get('severity', 'unknown')
        output = f"\n{'='*60}\n"
        output += f"SELL SIGNAL: {ticker} | Score: {score}/100 | Severity: {severity.upper()} | Phase {phase}\n"
        output += f"{'='*60}\n"

        if 'breakdown_level' in signal and signal['breakdown_level']:
            output += f"Breakdown Level: ${signal['breakdown_level']:.2f}\n"

        details = signal.get('details', {})
        if 'rs_slope' in details:
            output += f"RS Slope: {details['rs_slope']:.3f}\n"
        if 'volume_ratio' in details:
            output += f"Volume vs Avg: {details['volume_ratio']:.1f}x\n"

        output += f"\nReasons:\n"
        for reason in signal['reasons']:
            output += f"  • {reason}\n"

    return output
