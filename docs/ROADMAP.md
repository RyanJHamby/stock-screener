# Roadmap

Ideas, not commitments. None of these are built.

### Short-Term (Next 3 Months)

- [ ] **Backtesting Engine**
  - Simulate historical trades using phase transitions
  - Calculate win rate, profit factor, max drawdown
  - Optimize signal thresholds based on historical performance
  - Compare against buy-and-hold SPY baseline

- [ ] **Enhanced Reporting**
  - Add charts to daily report (SPY trend, market breadth, top signals)
  - Email delivery with HTML formatting
  - Slack integration with interactive buttons
  - Web dashboard for historical tracking

- [ ] **Smart Alerts**
  - Real-time alerts when positions hit stop levels
  - Notify when new high-score buy signals appear
  - Alert on market regime changes (SPY phase transitions)

### Medium-Term (3-6 Months)

- [ ] **Multi-Timeframe Analysis**
  - Add weekly phase classification (longer-term trend)
  - Combine daily + weekly phases for higher-conviction signals
  - Filter out counter-trend trades (daily bullish, weekly bearish)

- [ ] **Sector Rotation**
  - Track which sectors are leading/lagging
  - Adjust signal thresholds based on sector strength
  - Identify sector rotation opportunities

- [ ] **Options Integration**
  - Fetch option chain data for buy signals
  - Recommend covered call strikes for profitable positions
  - Identify protective put opportunities for Phase 3 stocks

- [ ] **Paper Trading**
  - Simulate trades in paper account
  - Track P&L of generated signals
  - Validate system performance before real capital

### Long-Term (6-12 Months)

- [ ] **Machine Learning Enhancement**
  - Train ML model on historical phase transitions
  - Predict probability of Phase 1 → 2 breakout success
  - Improve signal ranking using learned features

- [ ] **Alternative Data Sources**
  - Integrate insider trading data (SEC Form 4)
  - Add institutional ownership changes (13F filings)
  - Sentiment analysis from news/social media

- [ ] **Portfolio Construction**
  - Optimal position sizing based on volatility
  - Correlation-based diversification
  - Risk parity allocation across sectors

- [ ] **Execution Optimization**
  - Optimal entry timing (limit orders vs market orders)
  - Partial entry strategies (scale in over multiple days)
  - Bracket orders (auto-set stops and targets)

### Infrastructure

- [ ] **Database Migration**
  - Move from file-based cache to PostgreSQL
  - Enable complex queries (sector rotation, correlation analysis)
  - Faster lookups for backtesting

- [ ] **Real-Time Data**
  - Integrate with real-time data provider (IEX Cloud, Polygon)
  - Intraday phase classification (15-min bars)
  - Live stop loss monitoring

- [ ] **Web UI**
  - Interactive dashboard for browsing signals
  - Position tracker with live P&L
  - Backtest explorer with equity curves
