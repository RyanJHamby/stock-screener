# Quant Analysis & Execution Engine

## Overview

This is an autonomous **Phase-based stock screening system** that implements a rigorous 4-phase market cycle framework to identify high-probability buy and sell signals.

The system combines:
- **Technical Analysis**: Phase classification, SMAs, breakout detection, volume analysis
- **Relative Strength**: RS vs SPY with trend analysis
- **Fundamental Analysis**: Quarterly revenue, EPS, margins, inventory levels
- **Market Context**: SPY trend classification and market breadth metrics

## System Architecture

### Core Modules

1. **phase_indicators.py** - Technical indicator calculations
   - Phase classification (1-4)
   - SMA calculations with slope analysis
   - Relative Strength vs SPY
   - Volatility contraction detection
   - Breakout detection

2. **signal_engine.py** - Buy/sell signal scoring
   - Buy signal scoring (0-100) with 70+ threshold
   - Sell signal scoring (0-100) with 60+ threshold
   - Weighted scoring across multiple factors

3. **fundamentals_fetcher.py** - Quarterly financial data
   - Revenue and EPS trends (YoY and QoQ)
   - Margin analysis
   - Inventory tracking
   - Fundamental snapshots

4. **benchmark.py** - Market context analysis
   - SPY trend classification
   - Market breadth calculation
   - Risk-on/Risk-off regime classification

5. **quant_engine.py** - Main orchestrator
   - Coordinates all analysis
   - Generates daily reports
   - Handles data fetching and caching

## Phase System

### Phase 1: Base Building / Compression
- 50 SMA flat or turning up slightly
- 200 SMA flat
- Price trading tightly
- Volatility contracting
- Volume below average
- Support forming

### Phase 2: Uptrend / Breakout ✓ BUY ZONE
- Price closes above 50 SMA
- 50 SMA > 200 SMA
- Both SMAs sloping upward
- Breakout above resistance
- Volume expansion
- **PRIMARY BUY PHASE**

### Phase 3: Distribution / Top
- Price extended far above 50 SMA
- Momentum weakening
- Failed breakouts
- Volume distribution patterns
- Flattening of 50 SMA

### Phase 4: Downtrend ✗ SELL ZONE
- Price closes below 50 and 200 SMA
- 50 SMA < 200 SMA
- Both slopes downward
- Lower lows, lower highs
- **SELL SIGNALS ACTIVE**

## Buy Signal Scoring (0-100)

A stock must score **≥70** to be included in the buy list.

### Scoring Components:

1. **Trend Structure (40 points)**
   - Phase 2 confirmation: 30 pts
   - Phase 1→2 transition: 25 pts
   - Breakout detection: +10 pts
   - Over-extension penalty: -10 pts

2. **Volume Confirmation (20 points)**
   - Volume ≥1.5x average: 20 pts
   - Volume ≥1.3x average: 15 pts
   - Volume ≥1.1x average: 10 pts
   - Low volume: 0 pts

3. **Relative Strength Slope (20 points)**
   - RS slope >2.0: 20 pts
   - RS slope >1.0: 15 pts
   - RS slope >0.5: 10 pts
   - RS slope >0: 5 pts
   - Negative RS: 0 pts

4. **Volatility Contraction Quality (20 points)**
   - Scaled based on contraction quality (0-100%)

5. **Fundamental Penalty (-10 points)**
   - Revenue declining: -5 pts
   - EPS declining: -5 pts
   - Inventory building rapidly: -5 pts

## Sell Signal Scoring (0-100)

A stock must score **≥60** to be included in the sell list.

### Scoring Components:

1. **Breakdown Structure (60 points)**
   - Phase 2→3/4 transition: 30 pts
   - Break below 50 SMA: up to 20 pts
   - 50 SMA turning down: 10 pts

2. **Volume Confirmation (30 points)**
   - High volume breakdown ≥1.5x: 30 pts
   - Elevated volume ≥1.3x: 20 pts
   - Moderate volume: 10 pts

3. **RS Weakness (10 points)**
   - Sharp RS decline <-2.0: 10 pts
   - RS declining: 5-7 pts

## Usage

### Quick Test

```bash
python test_quant_engine.py
```

### Run with Config File

```bash
python run_quant_engine.py
```

The default config (`config.yaml`) contains a curated stock universe.

### Run with Custom Tickers

```bash
python run_quant_engine.py --tickers AAPL MSFT GOOGL NVDA TSLA
```

### Command Line Options

```bash
python run_quant_engine.py --help

Options:
  --config PATH        Path to config file (default: config.yaml)
  --tickers TICKER...  Override config with specific tickers
  --no-save           Do not save results to file
  --cache-dir PATH    Cache directory (default: ./data/cache)
```

## Configuration

Edit `config.yaml` to customize:

```yaml
# Stock Universe
stock_universe:
  - AAPL
  - MSFT
  # ... add more tickers

# Parameters
parameters:
  min_buy_score: 70        # Minimum buy signal score
  min_sell_score: 60       # Minimum sell signal score
  min_phase2_pct: 15.0     # Min % of stocks in Phase 2 for buy signals
  volume_threshold: 1.5    # Volume multiplier for breakouts
  max_extension_pct: 25.0  # Max distance from 50 SMA

# Output
output:
  save_to_file: true
  output_dir: "./data/results"
```

## Output Format

The engine produces a comprehensive daily report:

### 1. Benchmark Summary
- SPY trend classification (Phase 1-4)
- Market breadth metrics
- Risk-on/Risk-off regime
- Interpretation and recommendations

### 2. Buy List (Score ≥ 70)
For each buy signal:
- Ticker and score
- Phase classification
- Breakout price level
- RS slope
- Volume ratio
- Distance from 50 SMA
- Detailed reasons
- **Fundamental Snapshot** with:
  - Revenue trends (YoY, QoQ)
  - EPS trends
  - Margin analysis
  - Inventory analysis
  - Overall assessment

### 3. Sell List (Score ≥ 60)
For each sell signal:
- Ticker and severity
- Phase classification
- Breakdown level
- RS rollover metrics
- Volume confirmation
- Detailed reasons

## Edge Cases Handled

1. **No Buy Signals**: Outputs "NO BUYS TODAY" with reasons
2. **No Sell Signals**: Outputs "NO SELLS TODAY"
3. **Insufficient Data**: Stocks with <200 days of data are skipped
4. **Market Regime Filtering**: Buy signals suppressed in Risk-Off environments
5. **Missing Fundamentals**: System continues without penalty if data unavailable
6. **API Failures**: Automatic retry logic with exponential backoff
7. **Cache Management**: 24-hour cache expiry with manual clear option

## Data Caching

The system caches all fetched data to reduce API calls:

- **Cache Location**: `./data/cache/`
- **Cache Expiry**: 24 hours (configurable)
- **Cache Format**: Pickle files

To clear cache:
```python
from src.data.fetcher import YahooFinanceFetcher
fetcher = YahooFinanceFetcher()
fetcher.clear_cache()  # Clear all
fetcher.clear_cache('AAPL')  # Clear specific ticker
```

## Dependencies

Required packages (see `requirements.txt`):
- yfinance >= 0.2.32
- pandas >= 2.2.0
- numpy >= 1.24.0
- pyyaml >= 6.0

Install with:
```bash
pip install -r requirements.txt
```

## Rules Strictly Followed

The system implements ALL rules from your specification:

✓ Phase 1-4 classification with exact criteria
✓ Buy signals only on Phase 1→2 transition or Phase 2 breakouts
✓ Sell signals on Phase 2→3/4 transitions
✓ Volume confirmation (>150% of 20-day avg)
✓ RS vs SPY with 3-week slope requirement
✓ No buys if >25% extended from 50 SMA
✓ Weighted scoring: 40/20/20/20 split
✓ Score thresholds: ≥70 for buys, ≥60 for sells
✓ Fundamental fetching and analysis
✓ Inventory tracking (when available via API)
✓ Benchmark summary with market breadth
✓ Clean fallbacks: "NO BUYS TODAY" / "NO SELLS TODAY"

## Example Output

```
============================================================
QUANT ANALYSIS & EXECUTION ENGINE
Run Date: 2025-11-26 09:02:10
Stocks Analyzed: 5
============================================================

BENCHMARK SUMMARY
============================================================
SPY Trend Classification:
  Phase: 2 - Uptrend/Breakout
  Trend: Bullish
  Current Price: $675.02
  50 SMA: $669.53 (slope: 0.0793)
  200 SMA: $613.04 (slope: 0.0616)
  Confidence: 85%

Market Breadth (n=5):
  Phase 2 (Uptrend): 40.0%
  Breadth Quality: Good

Market Regime: RISK-ON (Moderate)

Interpretation:
  → Favorable environment for breakout trades
  → Focus on Phase 2 breakouts with strong RS

============================================================
BUY LIST (Score >= 70)
============================================================

BUY #1: TICKER | Score: 85/100
Phase: 2
Breakout Price: $150.25
RS Slope (3-week): 2.35
Volume vs Avg: 1.8x

Reasons:
  • In Phase 2 (Uptrend)
  • Base Breakout at $150.25
  • Strong volume: 1.8x average
  • Excellent RS momentum: 2.35

FUNDAMENTAL SNAPSHOT - TICKER
============================================================
✓ Revenue: ACCELERATING strongly (YoY: +25.3%, QoQ: +8.2%)
✓ EPS: STRONG growth (YoY: +32.1%, QoQ: +12.5%)
✓ Margins: EXPANDING (42.5%, +1.2pp QoQ)
• Inventory: Slight increase (+3.2% QoQ, ratio: 0.15)

Overall Assessment:
✓ Fundamentals SUPPORT technical breakout
```

## Future Enhancements

Potential additions:
- Database integration for tracking phase transitions over time
- Historical backtest framework
- Position sizing recommendations
- Stop-loss level calculations
- Email/Slack notifications for daily signals
- Interactive web dashboard
- Multi-timeframe analysis
- Sector rotation analysis

## License

Proprietary - Internal Use Only

## Support

For issues or questions, refer to the main project documentation or contact the development team.
