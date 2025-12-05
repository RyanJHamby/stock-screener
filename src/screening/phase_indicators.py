"""Phase-based technical indicators for the Quant Analysis Engine.

This module implements all technical indicators required for the Phase system:
- Phase classification (1-4)
- SMA calculations with slope analysis
- Relative Strength vs SPY
- Volatility contraction detection
- Breakout detection
- Volume analysis
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return pd.Series([np.nan] * len(prices), index=prices.index)
    return prices.rolling(window=period, min_periods=period).mean()


def calculate_slope(series: pd.Series, periods: int = 20) -> float:
    """Calculate the slope of a series over recent periods.

    Args:
        series: Price series to calculate slope
        periods: Number of periods to look back

    Returns:
        Slope as percentage change per day
    """
    if len(series) < periods or series.isna().all():
        return 0.0

    recent = series.iloc[-periods:].dropna()
    if len(recent) < 2:
        return 0.0

    # Linear regression slope
    x = np.arange(len(recent))
    y = recent.values

    if np.std(x) == 0:
        return 0.0

    slope = np.polyfit(x, y, 1)[0]

    # Convert to percentage per day
    avg_price = np.mean(y)
    if avg_price == 0:
        return 0.0

    slope_pct = (slope / avg_price) * 100

    return slope_pct


def calculate_relative_strength(stock_prices: pd.Series, spy_prices: pd.Series,
                                  period: int = 63) -> pd.Series:
    """Calculate Relative Strength vs SPY.

    RS = (Stock Price / SPY Price) * 100

    Args:
        stock_prices: Stock closing prices
        spy_prices: SPY closing prices
        period: Period for RS calculation (default 63 = ~3 months)

    Returns:
        Series of RS values
    """
    if len(stock_prices) == 0 or len(spy_prices) == 0:
        return pd.Series([np.nan] * len(stock_prices), index=stock_prices.index)

    # Align the series by DATE (not position) - stocks and SPY trade on same days
    # Use reindex to align SPY to stock dates, then forward fill any gaps
    spy_aligned = spy_prices.reindex(stock_prices.index, method='ffill')

    # Check if we have valid aligned data
    if spy_aligned.isna().all():
        logger.warning("SPY alignment failed - all NaN after reindex")
        return pd.Series([np.nan] * len(stock_prices), index=stock_prices.index)

    # Calculate RS
    rs = (stock_prices / spy_aligned) * 100

    # Fill any remaining NaN with forward fill
    rs = rs.fillna(method='ffill')

    return rs


def calculate_rs_slope(rs_series: pd.Series, periods: int = 15) -> float:
    """Calculate the slope of RS over recent periods (3-week slope).

    Args:
        rs_series: Relative strength series
        periods: Number of periods (default 15 = ~3 weeks)

    Returns:
        RS slope as float
    """
    return calculate_slope(rs_series, periods)


def detect_volatility_contraction(prices: pd.Series, window: int = 20) -> Dict[str, any]:
    """Detect volatility contraction (squeeze).

    Measures:
    - ATR contraction
    - Bollinger Band width narrowing
    - Range compression

    Args:
        prices: Price series
        window: Lookback window

    Returns:
        Dict with contraction metrics
    """
    if len(prices) < window * 2:
        return {
            'is_contracting': False,
            'contraction_quality': 0.0,
            'current_volatility': 0.0
        }

    # Calculate rolling standard deviation (volatility proxy)
    volatility = prices.rolling(window=window).std()

    if len(volatility.dropna()) < 2:
        return {
            'is_contracting': False,
            'contraction_quality': 0.0,
            'current_volatility': 0.0
        }

    current_vol = volatility.iloc[-1]
    avg_vol = volatility.iloc[-window*2:-window].mean()

    # Contraction = current volatility is below average
    contraction_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    is_contracting = contraction_ratio < 0.7  # Current vol < 70% of average

    # Quality score: lower ratio = higher quality
    quality = max(0, min(100, (1 - contraction_ratio) * 100))

    return {
        'is_contracting': is_contracting,
        'contraction_quality': round(quality, 2),
        'current_volatility': round(current_vol, 2),
        'contraction_ratio': round(contraction_ratio, 2)
    }


def find_base_high(prices: pd.Series, window: int = 60) -> Optional[float]:
    """Find the consolidation/base high over recent window.

    Args:
        prices: Price series
        window: Lookback window for base formation

    Returns:
        Base high price level
    """
    if len(prices) < window:
        return None

    recent_high = prices.iloc[-window:].max()
    return float(recent_high)


def find_pivot_high(prices: pd.Series, window: int = 20) -> Optional[float]:
    """Find recent pivot high (resistance level).

    Args:
        prices: Price series
        window: Lookback window

    Returns:
        Pivot high price level
    """
    if len(prices) < window:
        return None

    pivot = prices.iloc[-window:].max()
    return float(pivot)


def calculate_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
    """Calculate current volume vs average volume ratio.

    Args:
        volumes: Volume series
        period: Period for average

    Returns:
        Ratio (current / average)
    """
    if len(volumes) < period + 1:
        return 1.0

    current = volumes.iloc[-1]
    avg = volumes.iloc[-period-1:-1].mean()

    if avg == 0:
        return 1.0

    return current / avg


def calculate_distance_from_sma(price: float, sma: float) -> float:
    """Calculate percentage distance from SMA.

    Args:
        price: Current price
        sma: SMA value

    Returns:
        Percentage distance
    """
    if sma == 0:
        return 0.0

    return ((price - sma) / sma) * 100


def classify_phase(price_data: pd.DataFrame, current_price: float) -> Dict[str, any]:
    """Classify current market phase (1-4) based on price action rules.

    Phase 1: Base Building / Compression
    - 50 SMA flat or turning up slightly
    - 200 SMA flat
    - Price trading tightly
    - Volatility contracting
    - Volume below average

    Phase 2: Uptrend / Breakout
    - Price > 50 SMA
    - 50 SMA > 200 SMA
    - Both SMAs sloping upward
    - Breakout above resistance
    - Volume expansion

    Phase 3: Distribution / Top
    - Price extended above 50 SMA
    - Momentum weakening
    - Flattening of 50 SMA

    Phase 4: Downtrend
    - Price < 50 and 200 SMA
    - 50 SMA < 200 SMA
    - Both slopes downward

    Args:
        price_data: DataFrame with OHLCV data
        current_price: Current stock price

    Returns:
        Dict with phase info
    """
    if len(price_data) < 200:
        return {
            'phase': 0,
            'phase_name': 'Insufficient Data',
            'confidence': 0.0,
            'reasons': ['Need at least 200 days of data']
        }

    close = price_data['Close']
    volume = price_data.get('Volume', pd.Series([]))

    # Calculate SMAs
    sma_50 = calculate_sma(close, 50)
    sma_200 = calculate_sma(close, 200)

    if sma_50.isna().all() or sma_200.isna().all():
        return {
            'phase': 0,
            'phase_name': 'Insufficient Data',
            'confidence': 0.0,
            'reasons': ['Cannot calculate SMAs']
        }

    sma_50_val = sma_50.iloc[-1]
    sma_200_val = sma_200.iloc[-1]

    # Calculate slopes
    slope_50 = calculate_slope(sma_50, 20)
    slope_200 = calculate_slope(sma_200, 20)

    # Volatility analysis
    vol_data = detect_volatility_contraction(close, 20)

    # Volume analysis
    if len(volume) > 20:
        avg_volume = volume.iloc[-20:].mean()
        current_volume = volume.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    else:
        volume_ratio = 1.0

    reasons = []
    confidence = 0.0

    # Phase 4: Downtrend (check first)
    if (current_price < sma_50_val and
        current_price < sma_200_val and
        sma_50_val < sma_200_val):

        phase = 4
        phase_name = 'Downtrend'
        reasons.append(f'Price ({current_price:.2f}) below both 50 SMA ({sma_50_val:.2f}) and 200 SMA ({sma_200_val:.2f})')
        reasons.append(f'50 SMA below 200 SMA (Death Cross)')
        confidence = 70

        if slope_50 < 0 and slope_200 < 0:
            reasons.append('Both SMAs declining')
            confidence += 20

        if slope_50 < 0:
            confidence += 10

    # Phase 2: Uptrend / Breakout
    elif (current_price > sma_50_val and
          sma_50_val > sma_200_val and
          slope_50 > 0):

        phase = 2
        phase_name = 'Uptrend/Breakout'
        reasons.append(f'Price ({current_price:.2f}) above 50 SMA ({sma_50_val:.2f})')
        reasons.append(f'50 SMA above 200 SMA (Golden Cross)')
        reasons.append(f'50 SMA rising (slope: {slope_50:.3f}%)')
        confidence = 70

        if slope_200 > 0:
            reasons.append(f'200 SMA also rising (slope: {slope_200:.3f}%)')
            confidence += 15

        if volume_ratio > 1.2:
            reasons.append(f'Volume expansion ({volume_ratio:.1f}x average)')
            confidence += 15

    # Phase 3: Distribution / Top
    elif (current_price > sma_50_val and
          calculate_distance_from_sma(current_price, sma_50_val) > 25):

        phase = 3
        phase_name = 'Distribution/Top'
        distance = calculate_distance_from_sma(current_price, sma_50_val)
        reasons.append(f'Price extended {distance:.1f}% above 50 SMA')
        confidence = 60

        if slope_50 < 0.05:  # Flattening
            reasons.append('50 SMA flattening')
            confidence += 20

        if abs(slope_50) < abs(slope_200) * 0.5:
            reasons.append('Momentum weakening')
            confidence += 20

    # Phase 1: Base Building
    else:
        phase = 1
        phase_name = 'Base Building'
        reasons.append('Price in consolidation pattern')
        confidence = 50

        if abs(slope_50) < 0.1:
            reasons.append(f'50 SMA flat (slope: {slope_50:.3f}%)')
            confidence += 15

        if abs(slope_200) < 0.05:
            reasons.append(f'200 SMA flat (slope: {slope_200:.3f}%)')
            confidence += 10

        if vol_data['is_contracting']:
            reasons.append(f'Volatility contracting ({vol_data["contraction_quality"]:.0f}% quality)')
            confidence += 15

        if volume_ratio < 1.0:
            reasons.append(f'Volume below average ({volume_ratio:.1f}x)')
            confidence += 10

    return {
        'phase': phase,
        'phase_name': phase_name,
        'confidence': min(confidence, 100),
        'reasons': reasons,
        'sma_50': round(sma_50_val, 2),
        'sma_200': round(sma_200_val, 2),
        'slope_50': round(slope_50, 4),
        'slope_200': round(slope_200, 4),
        'distance_from_50sma': round(calculate_distance_from_sma(current_price, sma_50_val), 2),
        'volatility_contraction': vol_data
    }


def detect_breakout(price_data: pd.DataFrame, current_price: float,
                     phase_info: Dict) -> Dict[str, any]:
    """Detect if a breakout is occurring.

    Args:
        price_data: DataFrame with OHLCV data
        current_price: Current price
        phase_info: Phase classification info

    Returns:
        Dict with breakout info
    """
    if phase_info['phase'] not in [1, 2]:
        return {
            'is_breakout': False,
            'breakout_level': None,
            'breakout_type': None
        }

    close = price_data['Close']

    # Find resistance levels
    base_high = find_base_high(close, 60)
    pivot_high = find_pivot_high(close, 20)
    sma_50 = phase_info.get('sma_50')

    breakout_level = None
    breakout_type = None
    is_breakout = False

    # Check breakout above base high
    if base_high and current_price > base_high:
        is_breakout = True
        breakout_level = base_high
        breakout_type = 'Base Breakout'

    # Check breakout above pivot
    elif pivot_high and current_price > pivot_high and pivot_high < base_high:
        is_breakout = True
        breakout_level = pivot_high
        breakout_type = 'Pivot Breakout'

    # Check breakout above 50 SMA
    elif sma_50 and current_price > sma_50:
        # Only count if recently crossed
        if close.iloc[-2] < sma_50 < current_price:
            is_breakout = True
            breakout_level = sma_50
            breakout_type = '50 SMA Breakout'

    return {
        'is_breakout': is_breakout,
        'breakout_level': round(breakout_level, 2) if breakout_level else None,
        'breakout_type': breakout_type
    }
