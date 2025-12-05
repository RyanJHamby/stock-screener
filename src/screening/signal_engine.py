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


def calculate_stop_loss(
    price_data: pd.DataFrame,
    current_price: float,
    phase_info: Dict,
    phase: int
) -> float:
    """Calculate logical stop loss level for swing trading.

    Stop loss placement rules:
    - Phase 2: Below recent swing low or 50 SMA (whichever is closer), typically 6-8% risk
    - Phase 1: Below base/consolidation low, typically 7-10% risk
    - Maximum risk: 10% from current price (wider stops = don't take trade)

    Args:
        price_data: OHLCV data
        current_price: Current price
        phase_info: Phase classification dict
        phase: Phase number (1 or 2)

    Returns:
        Stop loss price level
    """
    sma_50 = phase_info.get('sma_50', 0)

    if phase == 2:
        # Stage 2: Use 50 SMA or recent swing low, whichever is higher (tighter stop)
        # Look for lowest low in last 10 days (recent pullback low)
        if len(price_data) >= 10:
            recent_low = price_data['Low'].iloc[-10:].min()
        else:
            recent_low = price_data['Low'].min()

        # Stop should be below recent low with buffer (0.5%)
        swing_low_stop = recent_low * 0.995

        # Or below 50 SMA with buffer (1%)
        sma_stop = sma_50 * 0.99 if sma_50 > 0 else swing_low_stop

        # Use the higher of the two (tighter stop = less risk)
        stop_loss = max(swing_low_stop, sma_stop)

        # But don't place stop too tight (min 3% risk) or too loose (max 10% risk)
        risk_pct = (current_price - stop_loss) / current_price
        if risk_pct < 0.03:  # Too tight
            stop_loss = current_price * 0.97
        elif risk_pct > 0.10:  # Too loose
            stop_loss = current_price * 0.90

    else:  # Phase 1
        # Stage 1: Stop below base/consolidation low
        # Use lowest low in last 30 days (base low)
        if len(price_data) >= 30:
            base_low = price_data['Low'].iloc[-30:].min()
        else:
            base_low = price_data['Low'].min()

        # Stop below base low with buffer (1%)
        stop_loss = base_low * 0.99

        # Max 10% risk rule
        risk_pct = (current_price - stop_loss) / current_price
        if risk_pct > 0.10:
            stop_loss = current_price * 0.90

    return stop_loss


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

    Scoring Components (0-110):
    - Trend structure/Stage quality: 40 points
    - Fundamentals: 40 points (growth, margins, inventory)
    - Relative Strength: 10 points (market-relative performance)
    - Volume behavior: 10 points (directional context matters!)
    - Risk/Reward: 5 points
    - Entry quality: 5 points

    Threshold: >= 70 for signals

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

    # A) Base Stage 2 quality (30 points max) - LINEAR FORMULAS
    if phase == 2:
        # Not all Stage 2 stocks are equal! Grade by strength
        stage2_quality = 0

        # How far above SMAs? (15 pts) - Linear from 0% to 15%+
        # Formula: min(15, (distance_50 * 0.6) + (distance_200 * 0.4))
        distance_component = min(15, max(0,
            (distance_50 / 15.0 * 10) +  # 0-15% → 0-10 pts
            (distance_200 / 20.0 * 5)     # 0-20% → 0-5 pts
        ))
        stage2_quality += distance_component

        if distance_50 >= 10:
            reasons.append(f'Strong Stage 2: {distance_50:.1f}% above 50 SMA')
        elif distance_50 >= 3:
            reasons.append(f'Good Stage 2: {distance_50:.1f}% above 50 SMA')
        elif distance_50 >= 0:
            reasons.append(f'Weak Stage 2: {distance_50:.1f}% above 50 SMA')
        else:
            reasons.append(f'Very weak Stage 2: {distance_50:.1f}% from 50 SMA')

        # SMA slopes - are SMAs rising? (15 pts) - Linear from 0 to 0.08+
        # Formula: (slope_50/0.08 * 10) + (slope_200/0.05 * 5), capped at 15
        slope_component = min(15, max(0,
            (slope_50 / 0.08 * 10) +   # 0-0.08 → 0-10 pts
            (slope_200 / 0.05 * 5)      # 0-0.05 → 0-5 pts
        ))
        stage2_quality += slope_component

        if slope_50 > 0.05:
            reasons.append(f'SMAs rising strongly (50:{slope_50:.3f}, 200:{slope_200:.3f})')
        elif slope_50 > 0.02:
            reasons.append(f'SMAs rising moderately')
        elif slope_50 > 0:
            reasons.append(f'SMAs rising weakly')
        else:
            reasons.append('⚠ SMAs flat or declining')

        trend_score += stage2_quality

    elif phase == 1:
        # Stage 1 → Stage 2 transition potential (graded 0-25 points)
        transition_score = 0

        # How close to breaking out? (12 pts) - Linear from -10% to +5%
        # Formula: ((distance_50 + 10) / 15) * 12, capped at 12
        proximity_score = min(12, max(0, ((distance_50 + 10) / 15.0) * 12))
        transition_score += proximity_score

        if distance_50 >= -2:
            reasons.append(f'Near 50 SMA breakout ({distance_50:.1f}%)')
        elif distance_50 >= -5:
            reasons.append(f'Approaching 50 SMA ({distance_50:.1f}%)')
        else:
            reasons.append(f'Building base ({distance_50:.1f}% below 50 SMA)')

        # SMA setup - golden cross strength (13 pts) - Linear based on SMA separation
        # Formula: ((sma_50 - sma_200) / sma_200) * 200 * slope_factor, capped at 13
        sma_ratio = (sma_50 - sma_200) / sma_200 if sma_200 > 0 else 0
        slope_factor = min(1.0, max(0, slope_50 / 0.03))  # 0-0.03 slope → 0-1 multiplier
        sma_setup_score = min(13, max(0, sma_ratio * 200 * slope_factor))
        transition_score += sma_setup_score

        if sma_50 > sma_200 and slope_50 > 0.02:
            reasons.append(f'Strong golden cross setup (50 SMA {sma_ratio*100:.1f}% above 200)')
        elif sma_50 > sma_200:
            reasons.append(f'Golden cross present')
        elif sma_50 > sma_200 * 0.98:
            reasons.append('Approaching golden cross')
        else:
            reasons.append('50 SMA below 200 SMA')

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

    score += min(trend_score, 40)  # 40 points for technical trend
    details['trend_score'] = min(trend_score, 40)

    # ========================================================================
    # 2. FUNDAMENTALS (40 points) - Equal weight with technical
    # ========================================================================
    fundamental_score = 0

    if fundamentals:
        # A) Growth trends (20 points) - LINEAR based on actual YoY %
        # Get actual growth rates if available (None = missing data)
        revenue_yoy = fundamentals.get('revenue_yoy_change')  # None or float
        eps_yoy = fundamentals.get('eps_yoy_change')  # None or float

        # Revenue component (10 pts) - Linear from -20% to +40%
        # Formula: ((revenue_yoy + 20) / 60) * 10, capped at 10
        if revenue_yoy is not None:
            revenue_score = min(10, max(0, ((revenue_yoy + 20) / 60.0) * 10))
        else:
            revenue_score = 5  # Neutral if missing (50% of max)
        fundamental_score += revenue_score

        # EPS component (10 pts) - Linear from -20% to +60%
        # Formula: ((eps_yoy + 20) / 80) * 10, capped at 10
        if eps_yoy is not None:
            eps_score = min(10, max(0, ((eps_yoy + 20) / 80.0) * 10))
        else:
            eps_score = 5  # Neutral if missing (50% of max)
        fundamental_score += eps_score

        # Describe the growth (handle None values)
        if revenue_yoy is not None and eps_yoy is not None:
            if revenue_yoy > 25 and eps_yoy > 40:
                reasons.append(f'✓ Accelerating growth (Rev: {revenue_yoy:.0f}%, EPS: {eps_yoy:.0f}%)')
            elif revenue_yoy > 10 and eps_yoy > 15:
                reasons.append(f'Strong growth (Rev: {revenue_yoy:.0f}%, EPS: {eps_yoy:.0f}%)')
            elif revenue_yoy > 0 and eps_yoy > 0:
                reasons.append(f'Positive growth (Rev: {revenue_yoy:.0f}%, EPS: {eps_yoy:.0f}%)')
            elif revenue_yoy > -5 and eps_yoy > -5:
                reasons.append(f'Growth stalling (Rev: {revenue_yoy:.0f}%, EPS: {eps_yoy:.0f}%)')
            else:
                reasons.append(f'⚠ Declining (Rev: {revenue_yoy:.0f}%, EPS: {eps_yoy:.0f}%)')
        elif revenue_yoy is not None:
            reasons.append(f'Revenue trend: {revenue_yoy:+.0f}% YoY (EPS data missing)')
        elif eps_yoy is not None:
            reasons.append(f'EPS trend: {eps_yoy:+.0f}% YoY (Revenue data missing)')
        else:
            reasons.append('Growth data unavailable (neutral score)')

        # B) Inventory signal (10 points) - LINEAR based on actual QoQ %
        inv_qoq_change = fundamentals.get('inventory_qoq_change')  # None or float

        # Formula: 10 - (inv_qoq_change / 20) * 10, range 0-10
        # -20% inventory draw = 20 pts (capped at 10)
        # 0% = 10 pts (neutral)
        # +20% buildup = 0 pts
        if inv_qoq_change is not None:
            inventory_score = min(10, max(0, 10 - (inv_qoq_change / 20.0) * 10))
            fundamental_score += inventory_score

            if inv_qoq_change < -5:
                reasons.append(f'✓ Inventory drawing ({inv_qoq_change:.1f}% QoQ - strong demand)')
            elif inv_qoq_change < 5:
                reasons.append(f'Inventory neutral ({inv_qoq_change:.1f}% QoQ)')
            elif inv_qoq_change < 15:
                reasons.append(f'⚠ Inventory building ({inv_qoq_change:.1f}% QoQ)')
            else:
                reasons.append(f'⚠ Inventory building rapidly ({inv_qoq_change:.1f}% QoQ - demand concern)')
        else:
            # No inventory data - use neutral score (50% of max = 5 pts)
            inventory_score = 5
            fundamental_score += inventory_score
            # Don't add to reasons - many companies don't have inventory

        # C) Profit margins expansion (10 points bonus)
        # TODO: Add when margin data available
        fundamental_score += 10  # Placeholder - assume neutral

        details['fundamental_score'] = fundamental_score
    else:
        # No fundamentals available - neutral score
        fundamental_score = 20  # Half of 40
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

        # Score based on volume ratio - LINEAR
        # Formula: 5 + (vol_ratio - 1) * 10, range 0-10
        # ratio 0.5 (heavy on down) = 0 pts
        # ratio 1.0 (equal) = 5 pts
        # ratio 1.5+ (heavy on up) = 10 pts
        vol_ratio = (avg_vol_up / avg_vol_down) if avg_vol_down > 0 else 1.0
        volume_score = min(10, max(0, 5 + (vol_ratio - 1.0) * 10))

        if vol_ratio >= 1.3:
            reasons.append(f'✓ Volume heavier on up days ({avg_vol_up/1e6:.1f}M vs {avg_vol_down/1e6:.1f}M, ratio {vol_ratio:.2f})')
        elif vol_ratio >= 1.1:
            reasons.append(f'Volume slightly heavier on up days (ratio {vol_ratio:.2f})')
        elif vol_ratio >= 0.9:
            reasons.append(f'Volume pattern neutral (ratio {vol_ratio:.2f})')
        else:
            reasons.append(f'⚠ Volume heavier on down days (ratio {vol_ratio:.2f} - distribution)')

        details['avg_vol_up'] = round(avg_vol_up, 0)
        details['avg_vol_down'] = round(avg_vol_down, 0)
        details['volume_score'] = volume_score
    else:
        volume_score = 5  # Neutral if no data
        details['volume_score'] = volume_score

    score += volume_score

    # ========================================================================
    # 4. RELATIVE STRENGTH (10 points) - Market-relative performance
    # ========================================================================
    # RS measures stock performance vs SPY (market-relative strength)
    # Different from technical trend which is absolute price structure
    # Strong RS = stock outperforming market

    rs_score = 0

    if len(rs_series) >= 20 and not rs_series.isna().all():
        rs_slope = calculate_rs_slope(rs_series, 20)
        details['rs_slope'] = round(rs_slope, 3)

        # Linear scoring based on RS slope
        # RS slope > 0.15 = 10 pts (strong outperformance)
        # RS slope = 0 = 5 pts (neutral)
        # RS slope < -0.15 = 0 pts (underperformance)
        # Formula: 5 + (rs_slope / 0.03) capped at 0-10
        rs_score = min(10, max(0, 5 + (rs_slope / 0.03)))

        if rs_slope > 0.10:
            reasons.append(f'✓ Strong RS: {rs_slope:.3f} (outperforming SPY)')
        elif rs_slope > 0.03:
            reasons.append(f'Positive RS: {rs_slope:.3f}')
        elif rs_slope > -0.03:
            reasons.append(f'Neutral RS: {rs_slope:.3f}')
        elif rs_slope > -0.10:
            reasons.append(f'Weak RS: {rs_slope:.3f}')
        else:
            reasons.append(f'⚠ Declining RS: {rs_slope:.3f} (underperforming SPY)')
    else:
        details['rs_slope'] = None
        rs_score = 5  # Neutral if missing

    score += rs_score
    details['rs_score'] = round(rs_score, 2)

    # ========================================================================
    # 5. STOP LOSS CALCULATION (not scored, but critical for risk mgmt)
    # ========================================================================
    stop_loss = calculate_stop_loss(price_data, current_price, phase_info, phase)
    details['stop_loss'] = stop_loss

    # ========================================================================
    # 6. RISK/REWARD RATIO (5 points) - Minimum 2:1 for good trades
    # ========================================================================
    rr_score = 0
    risk_amount = current_price - stop_loss if stop_loss else 0

    # Calculate reward potential (resistance or % target)
    if phase == 2:
        # Stage 2: Use 20% upside as target (conservative)
        reward_target = current_price * 1.20
    else:  # Phase 1
        # Stage 1: Use breakout level + 15% as target
        if breakout_info.get('is_breakout'):
            reward_target = breakout_info['breakout_level'] * 1.15
        else:
            reward_target = sma_50 * 1.15  # Target 50 SMA + 15%

    reward_amount = reward_target - current_price

    # Calculate R/R ratio
    if risk_amount > 0:
        rr_ratio = reward_amount / risk_amount

        # LINEAR scoring: 1:1 = 0 pts, 2:1 = 2.5 pts, 3:1 = 5 pts, 4:1+ = 5 pts
        # Formula: min(5, max(0, (rr_ratio - 1) * 2.5))
        rr_score = min(5, max(0, (rr_ratio - 1.0) * 2.5))

        details['risk_reward_ratio'] = round(rr_ratio, 2)
        details['risk_amount'] = round(risk_amount, 2)
        details['reward_amount'] = round(reward_amount, 2)
        details['reward_target'] = round(reward_target, 2)

        if rr_ratio >= 3.0:
            reasons.append(f'✓ Excellent R/R: {rr_ratio:.1f}:1 (${risk_amount:.2f} risk, ${reward_amount:.2f} reward)')
        elif rr_ratio >= 2.0:
            reasons.append(f'Good R/R: {rr_ratio:.1f}:1')
        elif rr_ratio >= 1.5:
            reasons.append(f'Acceptable R/R: {rr_ratio:.1f}:1')
        else:
            reasons.append(f'⚠ Poor R/R: {rr_ratio:.1f}:1 (need 2:1 minimum)')
    else:
        details['risk_reward_ratio'] = 0
        rr_score = 0

    score += rr_score
    details['rr_score'] = round(rr_score, 2)

    # ========================================================================
    # 7. ENTRY QUALITY (5 points) - Don't chase extended moves!
    # ========================================================================
    entry_score = 0

    # A) Not over-extended from 50 SMA (3 pts)
    # Formula: max(0, 3 - (distance_50 / 10) * 3), range 0-3
    # 0% from 50 SMA = 3 pts (at support)
    # 10%+ from 50 SMA = 0 pts (extended)
    extension_score = max(0, 3 - (max(0, distance_50) / 10.0) * 3)
    entry_score += extension_score

    # B) Near logical entry point (2 pts) - LINEAR
    if phase == 2:
        # Stage 2: Best entry near 50 SMA (0-5% above) = 2 pts, scaling down to 15% = 0 pts
        # Formula: max(0, 2 - (distance_50 / 15) * 2), range 0-2
        # 0% above 50 SMA = 2 pts (ideal pullback to support)
        # 5% above 50 SMA = 1.33 pts (still good)
        # 10% above 50 SMA = 0.67 pts (getting extended)
        # 15%+ above 50 SMA = 0 pts (too extended)
        proximity_score = max(0, 2 - (max(0, distance_50) / 15.0) * 2)
        entry_score += proximity_score

        if distance_50 <= 3:
            reasons.append(f'✓ Excellent entry zone: {distance_50:.1f}% above 50 SMA (near support)')
        elif distance_50 <= 7:
            reasons.append(f'Good entry zone: {distance_50:.1f}% above 50 SMA')
        elif distance_50 <= 12:
            reasons.append(f'Moderate entry: {distance_50:.1f}% above 50 SMA (getting extended)')
        else:
            reasons.append(f'⚠ Extended entry: {distance_50:.1f}% above 50 SMA (wait for pullback)')
    else:  # Phase 1
        # Stage 1: Best entry near breakout zone (-3% to +5% from 50 SMA) = 2 pts
        # Formula: max(0, 2 - abs(distance_50 - 1) / 5 * 2), range 0-2
        # Target zone is -3% to +5%, with ideal at +1%
        # +1% from 50 SMA = 2 pts (perfect breakout positioning)
        # -3% or +5% from 50 SMA = 0.4 pts (edge of ideal zone)
        # Beyond that = 0 pts
        ideal_position = 1.0  # 1% above 50 SMA is ideal for breakout
        deviation = abs(distance_50 - ideal_position)
        proximity_score = max(0, 2 - (deviation / 6.0) * 2)
        entry_score += proximity_score

        if distance_50 >= -1 and distance_50 <= 3:
            reasons.append(f'✓ Excellent breakout zone: {distance_50:.1f}% from 50 SMA')
        elif distance_50 >= -4 and distance_50 <= 6:
            reasons.append(f'Good entry zone: {distance_50:.1f}% from 50 SMA')
        elif distance_50 >= -7 and distance_50 <= 9:
            reasons.append(f'Approaching entry zone: {distance_50:.1f}% from 50 SMA')
        else:
            reasons.append(f'Outside ideal entry zone: {distance_50:.1f}% from 50 SMA')

    score += entry_score
    details['entry_score'] = round(entry_score, 2)

    # Final score (out of 100: 40 technical + 40 fundamental + 10 volume + 5 R/R + 5 entry)
    final_score = max(0, min(score, 100))

    # Determine if this is a valid buy signal (>= 60)
    is_buy = final_score >= 60

    return {
        'ticker': ticker,
        'is_buy': is_buy,
        'score': round(final_score, 1),
        'phase': phase,
        'breakout_price': breakout_info.get('breakout_level') if breakout_info['is_breakout'] else None,
        'stop_loss': round(stop_loss, 2) if stop_loss else None,
        'risk_reward_ratio': details.get('risk_reward_ratio', 0),
        'entry_quality': 'Good' if entry_score >= 4 else 'Extended' if entry_score >= 2 else 'Poor',
        'reasons': reasons,
        'details': details
    }


def score_sell_signal(
    ticker: str,
    price_data: pd.DataFrame,
    current_price: float,
    phase_info: Dict,
    rs_series: pd.Series,
    previous_phase: Optional[int] = None,
    fundamentals: Optional[Dict] = None
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
        fundamentals: Optional fundamental analysis dict

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
