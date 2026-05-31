# Trade Tracking Spreadsheet Template

## Purpose
Manual tracking spreadsheet for swing trades based on scanner signals.
Track entries, exits, risk management, and performance metrics.

---

## Column Setup (A-Z)

### TRADE IDENTIFICATION
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **A** | Trade # | Auto-increment | Unique ID (1, 2, 3...) |
| **B** | Date Entered | Date | Entry date |
| **C** | Ticker | Text | Stock symbol |
| **D** | Signal Score | Number | Scanner score (60-110) |
| **E** | Phase | 1 or 2 | Stage 1 or Stage 2 |

### ENTRY DATA
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **F** | Entry Price | $ | Actual fill price |
| **G** | Entry Quality | Good/Extended/Poor | From scanner |
| **H** | Shares | Number | Position size |
| **I** | Position Value | `=F*H` | Total capital deployed |

### RISK MANAGEMENT
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **J** | Stop Loss | $ | Initial stop level (from scanner) |
| **K** | Risk Per Share | `=F-J` | $ risk per share |
| **L** | Total Risk $ | `=K*H` | Total $ at risk |
| **M** | Risk % | `=(K/F)*100` | % risk from entry |
| **N** | Portfolio Risk % | `=L/[Portfolio]` | % of total portfolio at risk |

### TARGET & REWARD
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **O** | Target Price | $ | Initial profit target (from scanner) |
| **P** | Reward Per Share | `=O-F` | $ reward per share |
| **Q** | R/R Ratio | `=P/K` | Risk/Reward ratio (need 2:1+) |
| **R** | Potential Profit $ | `=P*H` | Total profit if target hit |

### EXIT DATA
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **S** | Date Exited | Date | Exit date (blank if open) |
| **T** | Exit Price | $ | Actual sell price |
| **U** | Exit Reason | Dropdown | Target/Stop/Trail/Signal/Time |
| **V** | Days Held | `=S-B` | Hold period |

### PROFIT/LOSS
| Column | Header | Formula/Type | Purpose |
|--------|--------|--------------|---------|
| **W** | Profit/Loss $ | `=(T-F)*H` | Actual P/L in dollars |
| **X** | P/L % | `=((T-F)/F)*100` | % gain or loss |
| **Y** | R-Multiple | `=W/L` | How many R's won/lost |
| **Z** | Commission | $ | Total fees (entry + exit) |
| **AA** | Net P/L $ | `=W-Z` | After commissions |

### TRADE NOTES
| Column | Header | Type | Purpose |
|--------|--------|------|---------|
| **AB** | Entry Notes | Text | Why entered, setup quality, market conditions |
| **AC** | Exit Notes | Text | Why exited, what happened, lessons learned |
| **AD** | Mistakes | Text | What could have been done better |

---

## Dropdown Lists

### Exit Reason Dropdown (Column U)
Create data validation with these options:
- **Target Hit** - Reached profit target
- **Stop Loss** - Hit initial stop
- **Trailing Stop** - Trailed stop up, then hit
- **Scanner Signal** - Got sell signal from scanner
- **Time Stop** - Held too long without progress
- **Market Weakness** - SPY Phase 3/4
- **Partial Exit** - Took some profit
- **News/Event** - Earnings, news, external event

### Entry Quality Dropdown (Column G)
- **Good** - Within 5% of support
- **Extended** - 5-10% extended
- **Poor** - >10% extended (chase)

---

## Summary Dashboard (Separate Sheet)

### Performance Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **Total Trades** | `=COUNTA(TradeSheet!A:A)-1` | - |
| **Open Trades** | `=COUNTBLANK(TradeSheet!S:S)` | - |
| **Closed Trades** | `=COUNTA(TradeSheet!S:S)-1` | - |
| **Win Rate %** | `=COUNTIF(TradeSheet!W:W,">0")/[Closed]*100` | >60% |
| **Average Win $** | `=AVERAGEIF(TradeSheet!W:W,">0")` | - |
| **Average Loss $** | `=AVERAGEIF(TradeSheet!W:W,"<0")` | - |
| **Win/Loss Ratio** | `=[Avg Win]/ABS([Avg Loss])` | >2:1 |
| **Total P/L $** | `=SUM(TradeSheet!AA:AA)` | Positive |
| **Average R-Multiple** | `=AVERAGE(TradeSheet!Y:Y)` | >1.0 |
| **Largest Win $** | `=MAX(TradeSheet!W:W)` | - |
| **Largest Loss $** | `=MIN(TradeSheet!W:W)` | - |
| **Average Hold Time** | `=AVERAGE(TradeSheet!V:V)` | 15-45 days |

### Risk Analysis

| Metric | Formula | Target |
|--------|---------|--------|
| **Average Position Size** | `=AVERAGE(TradeSheet!I:I)` | 3-7% portfolio |
| **Average Risk %** | `=AVERAGE(TradeSheet!M:M)` | 5-8% per trade |
| **Max Concurrent Positions** | Manual tracking | 5-8 |
| **Total Portfolio Exposure** | `=SUM([Open Positions])` | <40% |

### By Phase Performance

| Phase | Trades | Win Rate | Avg R | Total P/L |
|-------|--------|----------|-------|-----------|
| Phase 1 | `=COUNTIF(E:E,1)` | `=COUNTIFS(E:E,1,X:X,">0")/[Trades]` | `=AVERAGEIF(E:E,1,Y:Y)` | `=SUMIF(E:E,1,AA:AA)` |
| Phase 2 | `=COUNTIF(E:E,2)` | `=COUNTIFS(E:E,2,X:X,">0")/[Trades]` | `=AVERAGEIF(E:E,2,Y:Y)` | `=SUMIF(E:E,2,AA:AA)` |

### By Signal Score Range

| Score Range | Trades | Win Rate | Avg R |
|-------------|--------|----------|-------|
| 85-110 | `=COUNTIFS(D:D,">=85")` | `=COUNTIFS(D:D,">=85",X:X,">0")/[Trades]` | `=AVERAGEIFS(Y:Y,D:D,">=85")` |
| 75-84 | `=COUNTIFS(D:D,">=75",D:D,"<85")` | ... | ... |
| 65-74 | `=COUNTIFS(D:D,">=65",D:D,"<75")` | ... | ... |
| 60-64 | `=COUNTIFS(D:D,">=60",D:D,"<65")` | ... | ... |

---

## Monthly Performance Tracker

| Month | Trades | Winners | Losers | Win Rate | Total P/L | Avg R |
|-------|--------|---------|--------|----------|-----------|-------|
| Jan 2025 | | | | | | |
| Feb 2025 | | | | | | |
| ...     | | | | | | |

Formula for Win Rate: `=Winners/(Winners+Losers)*100`

---

## Example Trade Entry

| Column | Value | Notes |
|--------|-------|-------|
| A | 1 | First trade |
| B | 12/02/2025 | Entry date |
| C | AAPL | Ticker |
| D | 87 | Scanner score |
| E | 2 | Phase 2 |
| F | $175.50 | Entry price |
| G | Good | Near 50 SMA |
| H | 100 | Shares |
| I | $17,550 | Position value |
| J | $167.00 | Stop loss (4.8% risk) |
| K | $8.50 | Risk per share |
| L | $850 | Total risk |
| M | 4.8% | Risk % from entry |
| N | 1.7% | Portfolio risk (assuming $50k account) |
| O | $210.60 | Target (20% gain) |
| P | $35.10 | Reward per share |
| Q | 4.1:1 | R/R ratio (excellent) |
| R | $3,510 | Potential profit |
| S | (blank) | Still open |
| T | (blank) | Still open |
| U | (blank) | Still open |
| V | (blank) | Still open |
| W | (blank) | Still open |
| X | (blank) | Still open |
| Y | (blank) | Still open |
| Z | $14 | Commission estimate |
| AA | (blank) | Still open |
| AB | "Strong Stage 2, RS excellent, fundamentals accelerating. Market bullish. Good pullback to 50 SMA." | Entry reasoning |
| AC | (blank) | Will fill on exit |
| AD | (blank) | Will fill on exit |

---

## Trade Management Rules (Add to Spreadsheet)

### Position Sizing Based on Score
- **85-110**: Full position (5-7% of portfolio)
- **75-84**: 3/4 position (4-5% of portfolio)
- **65-74**: 1/2 position (2.5-3.5% of portfolio)
- **60-64**: 1/4 position or pilot (1-2% of portfolio)

### Stop Loss Management
1. **Initial**: Use scanner-calculated stop
2. **Breakeven**: Move to breakeven after 10% gain
3. **Trailing**: Trail stop to 50 SMA or swing lows
4. **Time Stop**: Exit if no progress after 3-4 weeks

### Profit Taking
1. **25% at 1R**: Take 1/4 off at 1:1 risk/reward
2. **25% at 2R**: Take another 1/4 at 2:1
3. **Trail remaining**: Let runners go with trailing stop

### When to Exit Early
- ❌ Phase changes to 3 (distribution)
- ❌ SPY enters Phase 3/4 (market weakness)
- ❌ Scanner generates sell signal
- ❌ Breaks below 50 SMA on high volume
- ❌ Parabolic move (vertical on chart)
- ❌ Negative news/earnings miss

---

## Tips for Using the Spreadsheet

### Daily Review
1. Update open positions with current prices
2. Check if any stops need adjusting (trail up)
3. Note any changes in market conditions

### Weekly Review
1. Calculate running win rate
2. Check average R-multiple (should be >1.0)
3. Review recent exits - what worked? What didn't?
4. Identify patterns in winners vs losers

### Monthly Review
1. Calculate monthly P/L
2. Review all trades - any bad habits forming?
3. Compare Phase 1 vs Phase 2 performance
4. Adjust position sizing if needed

### Red Flags to Watch
- ⚠️ Win rate dropping below 50%
- ⚠️ Average R-multiple below 1.0 (losing more than winning)
- ⚠️ Chasing extended entries (Entry Quality = Poor)
- ⚠️ Taking trades below 60 score
- ⚠️ Ignoring stop losses
- ⚠️ Position sizes too large (>7% portfolio)
- ⚠️ Too many concurrent positions (>8)

---

## Google Sheets / Excel Setup Instructions

### 1. Create New Spreadsheet
File → New Spreadsheet → Name it "Swing Trade Journal 2025"

### 2. Set Up Sheets
- **Sheet 1**: "Trades" (main tracking sheet)
- **Sheet 2**: "Dashboard" (performance summary)
- **Sheet 3**: "Monthly" (monthly performance)

### 3. Format Headers (Row 1)
- Bold text
- Background color: Light blue (#E3F2FD)
- Freeze first row: View → Freeze → 1 row

### 4. Number Formatting
- Columns F, J, K, L, O, P, R, T, W, Z, AA: Currency ($0.00)
- Columns M, N, X: Percentage (0.00%)
- Columns B, S: Date (MM/DD/YYYY)
- Column Q, Y: Number (0.00)

### 5. Conditional Formatting
**Column X (P/L %)**:
- Green if > 0
- Red if < 0
- Formula: `=X2>0` (green), `=X2<0` (red)

**Column D (Signal Score)**:
- Dark green: >= 85
- Light green: 75-84
- Yellow: 65-74
- Orange: 60-64

### 6. Data Validation
**Column U (Exit Reason)**: Create dropdown
- Data → Data Validation → List of items
- Add: Target Hit, Stop Loss, Trailing Stop, Scanner Signal, Time Stop, Market Weakness, Partial Exit, News/Event

**Column G (Entry Quality)**: Create dropdown
- List: Good, Extended, Poor

---

## Import from Scanner

When you get a signal from the scanner, copy these fields directly:

| Scanner Output | Spreadsheet Column |
|----------------|-------------------|
| Ticker | C |
| Score | D |
| Phase | E |
| Current Price | F (as entry if buying now) |
| Stop Loss | J |
| Risk/Reward Ratio | Q (for validation) |
| Entry Quality | G |
| Reward Target | O |

**Then manually add**:
- Number of shares (based on position sizing rules)
- Entry notes (why taking this trade)
- Date

---

## Sample Formulas

### Calculate Shares to Buy (based on $ risk)
```
= ROUND([Risk Per Trade $] / (Entry Price - Stop Loss), 0)
```

Example: Want to risk $500
```
= ROUND(500 / (175.50 - 167.00), 0)
= ROUND(500 / 8.50, 0)
= 59 shares
```

### Check if Trade Meets R/R Requirement
```
= IF(Q2 >= 2, "✓ Good", "✗ Skip")
```

### Days Until Stop Review (trail every 7 days)
```
= 7 - MOD(TODAY() - B2, 7)
```

---

This spreadsheet will give you complete visibility into:
- What's working (high score trades? Phase 2 better than Phase 1?)
- What's not working (chasing extended entries? Holding too long?)
- Your edge (average R-multiple, win rate by setup type)
- Risk management (position sizing, stop discipline)

Track EVERY trade. The data will reveal your strengths and weaknesses over time.
