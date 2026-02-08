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
    detect_breakout,
    validate_minervini_trend_template,
    calculate_sma
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
    fundamentals: Optional[Dict] = None,
    vcp_data: Optional[Dict] = None
) -> Dict[str, any]:
    """Score a buy signal for swing/position trading (NOT day trading).

    Based on Weinstein/O'Neil/Minervini Stage 2 methodology with gradual scoring.

    Scoring Components (0-125):
    - Trend structure/Stage quality: 40 points
    - Fundamentals: 40 points (growth, margins, inventory)
    - Risk/Reward: 15 points (asymmetric upside - key for growth!)
    - Relative Strength: 10 points (market-relative performance)
    - Volume behavior: 10 points (directional context matters!)
    - Entry quality: 5 points
    - VCP pattern bonus: +5 points (if valid VCP detected)

    Threshold: >= 70 for signals

    Args:
        ticker: Stock ticker
        price_data: OHLCV data
        current_price: Current price
        phase_info: Phase classification
        rs_series: Relative strength series
        fundamentals: Optional fundamental analysis
        vcp_data: Optional VCP pattern analysis

    Returns:
        Dict with buy signal score and details
    """
    phase = phase_info['phase']

    # MINERVINI REQUIREMENT: Only Phase 2 (confirmed Stage 2 uptrend)
    # Phase 1 stocks are NOT ready - they're still basing/accumulating
    if phase != 2:
        return {
            'ticker': ticker,
            'is_buy': False,
            'score': 0,
            'reason': f'Not in Phase 2 (currently Phase {phase}) - Minervini requires confirmed uptrend',
            'details': {}
        }

    # Validate Minervini Trend Template (SEPA)
    # This is the core entry criteria from "Trade Like a Stock Market Wizard"
    sma_200 = calculate_sma(price_data['Close'], 200)
    minervini = validate_minervini_trend_template(current_price, phase_info, sma_200)

    # STRICT FILTER: Must pass at least 7 of 8 Minervini criteria
    if not minervini['passes_template']:
        return {
            'ticker': ticker,
            'is_buy': False,
            'score': 0,
            'reason': f"Fails Minervini Trend Template ({minervini['criteria_passed']}/8 criteria passed)",
            'details': {'minervini': minervini}
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

    # At this point, we're guaranteed to be in Phase 2 (checked above)
    # Minervini only buys confirmed Stage 2 stocks

    # B) Breakout detection (10 points) - Enhanced with VCP
    breakout_info = detect_breakout(price_data, current_price, phase_info, vcp_data)
    if breakout_info['is_breakout']:
        trend_score += 10
        breakout_type = breakout_info['breakout_type']
        volume_confirmed = breakout_info.get('volume_confirmed', False)

        if volume_confirmed:
            reasons.append(f"🟢 {breakout_type} (volume confirmed)")
        else:
            reasons.append(f"🟡 {breakout_type} (low volume)")
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
    # 2. FUNDAMENTALS (40 points) - EQUAL WEIGHT REVENUE & EPS
    # Revenue Growth: 15 pts (requires 3Q of >5% QoQ for max score)
    # EPS Growth: 15 pts (equal importance to revenue)
    # Inventory: 10 pts (demand indicator)
    # ========================================================================
    fundamental_score = 0

    if fundamentals:
        # A) Growth trends (30 points total) - EQUAL WEIGHT
        # Revenue and EPS are equally important (15 pts each)

        # Get quarterly revenue data for trend analysis
        quarterly_revenue = fundamentals.get('quarterly_revenue', {})
        revenue_qoq = fundamentals.get('revenue_qoq_change')  # None or float
        revenue_yoy = fundamentals.get('revenue_yoy_change')  # None or float
        eps_yoy = fundamentals.get('eps_yoy_change')  # None or float

        # Calculate 3-quarter revenue trend using LINEAR SCORING
        revenue_trend_score = 0

        if quarterly_revenue and len(quarterly_revenue) >= 4:
            # Get last 4 quarters of revenue (sorted by date)
            import pandas as pd
            rev_series = pd.Series(quarterly_revenue).sort_index()

            if len(rev_series) >= 4:
                # Calculate QoQ changes for last 3 quarters
                q1_growth = ((rev_series.iloc[-1] - rev_series.iloc[-2]) / rev_series.iloc[-2] * 100) if rev_series.iloc[-2] != 0 else 0
                q2_growth = ((rev_series.iloc[-2] - rev_series.iloc[-3]) / rev_series.iloc[-3] * 100) if rev_series.iloc[-3] != 0 else 0
                q3_growth = ((rev_series.iloc[-3] - rev_series.iloc[-4]) / rev_series.iloc[-4] * 100) if rev_series.iloc[-4] != 0 else 0

                # Calculate average QoQ growth across 3 quarters
                avg_qoq_growth = (q1_growth + q2_growth + q3_growth) / 3.0

                # LINEAR SCALE: Map avg QoQ growth to 0-15 points
                # 0% or negative → 0 pts (no growth = no points)
                # +5% avg → 7.5 pts (your minimum threshold for good)
                # +10% avg → 15 pts (excellent - capped at max)
                # Formula: (avg_qoq / 10) * 15, capped at 0-15
                # Only positive growth gets points
                if avg_qoq_growth <= 0:
                    revenue_trend_score = 0
                else:
                    revenue_trend_score = min(15, (avg_qoq_growth / 10.0) * 15)

                # Add strong penalty if latest quarter is declining >2%
                if q1_growth < -2:
                    fundamental_score -= 15  # Penalty for recent decline
                    reasons.append(f'🔴 Revenue: Recent decline {q1_growth:.1f}% QoQ (3Q avg: {avg_qoq_growth:.1f}%, PENALTY)')
                # Color-code based on average and show progression
                elif avg_qoq_growth >= 5:
                    reasons.append(f'🟢 Revenue: 3Q avg {avg_qoq_growth:.1f}% QoQ ({q3_growth:.1f}% → {q2_growth:.1f}% → {q1_growth:.1f}%)')
                elif avg_qoq_growth >= 0:
                    reasons.append(f'🟡 Revenue: 3Q avg {avg_qoq_growth:.1f}% QoQ ({q3_growth:.1f}% → {q2_growth:.1f}% → {q1_growth:.1f}%)')
                else:
                    reasons.append(f'🔴 Revenue: 3Q avg {avg_qoq_growth:.1f}% QoQ ({q3_growth:.1f}% → {q2_growth:.1f}% → {q1_growth:.1f}%)')
        else:
            # No quarterly data - use YoY if available
            if revenue_yoy is not None and revenue_yoy != 0:
                # Same logic: 0% or negative = 0 pts, +20% YoY = 15 pts (max)
                if revenue_yoy <= 0:
                    revenue_trend_score = 0
                    reasons.append(f'🔴 Revenue: {revenue_yoy:.0f}% YoY declining (no QoQ data)')
                else:
                    revenue_trend_score = min(15, (revenue_yoy / 20.0) * 15)
                    if revenue_yoy >= 10:
                        reasons.append(f'🟢 Revenue: {revenue_yoy:.0f}% YoY (no QoQ data)')
                    else:
                        reasons.append(f'🟡 Revenue: {revenue_yoy:.0f}% YoY (no QoQ data)')
            else:
                revenue_trend_score = 0  # No data = 0 points
                reasons.append('🔴 Revenue data unavailable')

        fundamental_score += revenue_trend_score

        # EPS component (15 pts) - Equal importance to revenue
        # Formula: ((eps_yoy + 20) / 80) * 15, capped at 15
        # -20% EPS → 0 pts, 0% → 3.75 pts, +20% → 7.5 pts, +60% → 15 pts (max)
        if eps_yoy is not None and eps_yoy != 0:
            eps_score = min(15, max(0, ((eps_yoy + 20) / 80.0) * 15))

            if eps_yoy >= 50:
                reasons.append(f'🟢 EPS: +{eps_yoy:.0f}% YoY (strong earnings)')
            elif eps_yoy >= 20:
                reasons.append(f'🟢 EPS: +{eps_yoy:.0f}% YoY')
            elif eps_yoy >= 0:
                reasons.append(f'🟡 EPS: +{eps_yoy:.0f}% YoY')
            else:
                reasons.append(f'🔴 EPS: {eps_yoy:.0f}% YoY')
        else:
            eps_score = 7.5  # Neutral if missing (half of 15)
        fundamental_score += eps_score

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

        # SMOOTH LINEAR scoring based on RS slope (NO BUCKETS)
        # RS slope ranges typically from -0.30 to +0.30
        # Formula: 5 + (rs_slope * 16.67), capped at 0-10
        # Examples:
        #   rs_slope = +0.30 → 5 + (0.30 * 16.67) = 10.0 pts (max)
        #   rs_slope = +0.15 → 5 + (0.15 * 16.67) = 7.5 pts
        #   rs_slope =  0.00 → 5 + (0.00 * 16.67) = 5.0 pts (neutral)
        #   rs_slope = -0.15 → 5 + (-0.15 * 16.67) = 2.5 pts
        #   rs_slope = -0.30 → 5 + (-0.30 * 16.67) = 0.0 pts (min)
        rs_score = min(10, max(0, 5 + (rs_slope * 16.67)))

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
    # 6. RISK/REWARD RATIO (15 points) - CRITICAL for growth stocks!
    # ========================================================================
    # For growth stocks, asymmetric upside is essential
    # We want stocks with 3:1+ R/R ratios for maximum growth potential
    rr_score = 0
    risk_amount = current_price - stop_loss if stop_loss else 0

    # Calculate reward potential (more aggressive for growth stocks)
    if phase == 2:
        # Stage 2: Use 30% upside as target (aggressive growth target)
        reward_target = current_price * 1.30
    else:  # Phase 1
        # Stage 1: Use breakout level + 25% as target
        if breakout_info.get('is_breakout'):
            reward_target = breakout_info['breakout_level'] * 1.25
        else:
            reward_target = sma_50 * 1.25  # Target 50 SMA + 25%

    reward_amount = reward_target - current_price

    # Calculate R/R ratio
    if risk_amount > 0:
        rr_ratio = reward_amount / risk_amount

        # AGGRESSIVE LINEAR scoring for growth stocks:
        # < 2:1 = 0 pts (reject - not enough upside)
        # 2:1 = 3 pts (minimum acceptable)
        # 3:1 = 9 pts (good)
        # 4:1 = 12 pts (excellent)
        # 5:1+ = 15 pts (outstanding - maximum)
        # Formula: For R/R >= 2, score = min(15, (rr_ratio - 2) * 6 + 3)
        if rr_ratio < 2.0:
            rr_score = 0  # Reject poor R/R
        else:
            rr_score = min(15, ((rr_ratio - 2.0) * 6) + 3)

        details['risk_reward_ratio'] = round(rr_ratio, 2)
        details['risk_amount'] = round(risk_amount, 2)
        details['reward_amount'] = round(reward_amount, 2)
        details['reward_target'] = round(reward_target, 2)

        if rr_ratio >= 5.0:
            reasons.append(f'🟢 Outstanding R/R: {rr_ratio:.1f}:1 (${reward_amount:.2f} upside, ${risk_amount:.2f} risk)')
        elif rr_ratio >= 4.0:
            reasons.append(f'🟢 Excellent R/R: {rr_ratio:.1f}:1 (${reward_amount:.2f} upside, ${risk_amount:.2f} risk)')
        elif rr_ratio >= 3.0:
            reasons.append(f'🟢 Good R/R: {rr_ratio:.1f}:1 (${reward_amount:.2f} upside)')
        elif rr_ratio >= 2.0:
            reasons.append(f'🟡 Acceptable R/R: {rr_ratio:.1f}:1')
        else:
            reasons.append(f'🔴 Poor R/R: {rr_ratio:.1f}:1 (need 2:1+ for growth)')
    else:
        details['risk_reward_ratio'] = 0
        rr_score = 0

    score += rr_score
    details['rr_score'] = round(rr_score, 2)

    # ========================================================================
    # 7. ENTRY QUALITY (5 points) - Minervini Pivot Point Methodology
    # ========================================================================
    # Minervini's ideal entry is the PIVOT POINT - a breakout from a proper base
    # near 52-week highs on expanding volume, NOT just pullbacks to 50 SMA
    entry_score = 0

    # Calculate proximity to 52-week high (key Minervini metric)
    # phase_info contains 'week_52_high' from phase classification
    week_52_high = phase_info.get('week_52_high', current_price)
    distance_from_52w_high = ((current_price - week_52_high) / week_52_high * 100) if week_52_high > 0 else -100

    if phase == 2:
        # Stage 2 uptrend - score based on PIVOT POINT criteria
        # Minervini's rule: Within 25% of 52-week high is ideal
        # The CLOSER to 52-week high, the BETTER (indicates leadership)

        # Primary factor: Proximity to 52-week high (3 pts)
        if distance_from_52w_high >= -5:
            # At or near 52-week high (ideal pivot breakout zone)
            high_proximity_score = 3
            reasons.append(f'🟢 At 52W high: {abs(distance_from_52w_high):.1f}% from high (pivot zone)')
        elif distance_from_52w_high >= -15:
            # Within 15% of high (good - near pivot zone)
            # Linear from 3 pts (at -5%) to 2 pts (at -15%)
            high_proximity_score = 3 - ((abs(distance_from_52w_high) - 5) / 10.0) * 1
            reasons.append(f'🟢 Near 52W high: {abs(distance_from_52w_high):.1f}% from high')
        elif distance_from_52w_high >= -25:
            # Within 25% of high (acceptable - Minervini's threshold)
            # Linear from 2 pts (at -15%) to 1 pt (at -25%)
            high_proximity_score = 2 - ((abs(distance_from_52w_high) - 15) / 10.0) * 1
            reasons.append(f'🟡 Within 25% of 52W high: {abs(distance_from_52w_high):.1f}% from high')
        else:
            # More than 25% below high (lagging, not leading)
            high_proximity_score = 0
            reasons.append(f'🔴 Far from 52W high: {abs(distance_from_52w_high):.1f}% below (not a leader)')

        entry_score += high_proximity_score

        # Secondary factor: Distance from 50 SMA (2 pts)
        # Must be ABOVE 50 SMA, but distance less critical for pivot breakouts
        if distance_50 > 0 and distance_50 <= 20:
            # Above 50 SMA and not overextended (good)
            # Linear from 2 pts (at 0%) to 1 pt (at 20%)
            sma_score = 2 - (distance_50 / 20.0) * 1
        elif distance_50 > 20:
            # More than 20% above 50 SMA (getting extended)
            sma_score = max(0, 1 - ((distance_50 - 20) / 15.0) * 1)
        else:
            # Below 50 SMA (not in proper Stage 2)
            sma_score = 0

        entry_score += sma_score
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

    # ========================================================================
    # 8. VCP PATTERN BONUS (5 points) - Minervini's VCP Methodology
    # ========================================================================
    # Valid VCP patterns get bonus points as they indicate institutional accumulation
    # and high-probability setup formation
    vcp_bonus = 0

    if vcp_data and vcp_data.get('is_vcp'):
        # VCP detected - award bonus based on quality
        vcp_quality = vcp_data.get('vcp_quality', 0)

        if vcp_quality >= 80:
            # Exceptional VCP (80-100 quality)
            vcp_bonus = 5
            reasons.append(f"⭐ VCP pattern: {vcp_data.get('pattern_details', 'N/A')} (quality: {vcp_quality:.0f}/100)")
        elif vcp_quality >= 60:
            # Good VCP (60-80 quality)
            vcp_bonus = 3
            reasons.append(f"🟢 VCP pattern: {vcp_data.get('pattern_details', 'N/A')} (quality: {vcp_quality:.0f}/100)")
        else:
            # Marginal VCP (50-60 quality)
            vcp_bonus = 1
            reasons.append(f"🟡 VCP pattern: {vcp_data.get('pattern_details', 'N/A')} (quality: {vcp_quality:.0f}/100)")

        details['vcp_data'] = {
            'quality': vcp_quality,
            'contractions': vcp_data.get('contraction_count', 0),
            'pattern': vcp_data.get('pattern_details', ''),
            'base_length_weeks': vcp_data.get('base_length_weeks', 0),
            'volume_ratio': vcp_data.get('breakout_volume_ratio', 0),
            'quality_factors': vcp_data.get('quality_factors', [])
        }
    elif vcp_data and vcp_data.get('contraction_count', 0) > 0:
        # VCP not valid but some contractions detected
        reasons.append(f"🟡 Partial pattern: {vcp_data.get('pattern_details', 'N/A')}")
        details['vcp_data'] = {
            'quality': vcp_data.get('vcp_quality', 0),
            'contractions': vcp_data.get('contraction_count', 0),
            'pattern': vcp_data.get('pattern_details', '')
        }

    score += vcp_bonus
    details['vcp_bonus'] = round(vcp_bonus, 2)

    # Final score (out of 125: 40 technical + 40 fundamental + 15 R/R + 10 RS + 10 volume + 5 entry + 5 VCP)
    final_score = max(0, min(score, 125))

    # Determine if this is a valid buy signal (>= 60)
    is_buy = final_score >= 60

    # Add Minervini template details
    details['minervini_template'] = minervini

    return {
        'ticker': ticker,
        'is_buy': is_buy,
        'score': round(final_score, 1),
        'phase': phase,
        'minervini_template_score': minervini['template_score'],
        'minervini_criteria_passed': minervini['criteria_passed'],
        'breakout_price': breakout_info.get('breakout_level') if breakout_info['is_breakout'] else None,
        'stop_loss': round(stop_loss, 2) if stop_loss else None,
        'risk_reward_ratio': details.get('risk_reward_ratio', 0),
        'entry_quality': 'Good' if entry_score >= 3 else 'Extended' if entry_score >= 1.5 else 'Poor',
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
