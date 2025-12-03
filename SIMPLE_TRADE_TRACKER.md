# Simple Trade Tracker - Swing Trading

**Purpose**: Minimal spreadsheet for tracking swing trades from scanner signals.

---

## Column Setup (A-M) - 13 Columns Total

| Column | Header | Formula/Type | Notes |
|--------|--------|--------------|-------|
| **A** | Date | Date | Entry date |
| **B** | Ticker | Text | Stock symbol |
| **C** | Score | Number | Scanner score (60-110) |
| **D** | Entry $ | $ | Buy price |
| **E** | Stop $ | $ | Stop loss from scanner |
| **F** | Target $ | $ | Profit target |
| **G** | Shares | Number | Position size |
| **H** | Risk $ | `=(D-E)*G` | Total dollars at risk |
| **I** | R/R | From scanner | Risk/reward ratio |
| **J** | Exit Date | Date | Blank if open |
| **K** | Exit $ | $ | Sell price |
| **L** | P/L $ | `=(K-D)*G` | Profit or loss |
| **M** | Notes | Text | Why entered, why exited |

---

## Quick Stats (Bottom of Sheet)

Add these summary rows at the bottom:

| Metric | Formula |
|--------|---------|
| **Total Trades** | `=COUNTA(B:B)-1` |
| **Open Trades** | `=COUNTBLANK(J:J)-1` |
| **Win Rate %** | `=COUNTIF(L:L,">0")/(COUNTA(J:J)-1)*100` |
| **Total P/L** | `=SUM(L:L)` |
| **Avg Win** | `=AVERAGEIF(L:L,">0")` |
| **Avg Loss** | `=AVERAGEIF(L:L,"<0")` |

---

## Position Sizing Calculator

**How many shares to buy?**

If you want to risk $500 per trade:
```
Shares = $500 / (Entry Price - Stop Loss)
```

Example:
- Entry: $175.50
- Stop: $167.00
- Risk per share: $8.50
- Shares to buy: $500 / $8.50 = **59 shares**

---

## Import from Scanner

When you get a buy signal, copy these directly:

| Scanner → Spreadsheet |
|-----------------------|
| Ticker → Column B |
| Score → Column C |
| Current Price → Column D |
| Stop Loss → Column E |
| Target (20% above entry) → Column F |
| Risk/Reward → Column I |

**Then add manually**:
- Date (Column A)
- Shares (Column G) - use position sizing formula
- Notes (Column M) - why taking this trade

---

## Google Sheets Setup

1. **Create new sheet** named "Swing Trades 2025"
2. **Format headers** (Row 1): Bold, freeze row
3. **Number formats**:
   - Columns D, E, F, K: Currency `$0.00`
   - Columns H, L: Currency `$0.00`
   - Column I: Number `0.0`
   - Columns A, J: Date `MM/DD/YYYY`
4. **Conditional formatting** on Column L (P/L):
   - Green if > 0
   - Red if < 0

---

## Example Trade

| A | B | C | D | E | F | G | H | I | J | K | L | M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12/02/25 | AAPL | 87 | $175.50 | $167.00 | $210.60 | 59 | $501.50 | 4.1 | | | | Strong S2, RS excellent, good pullback to 50 SMA |

---

## Trade Management Rules

### Position Sizing by Score
- **85-110**: Full position (5-7% of portfolio)
- **75-84**: 3/4 position (4-5%)
- **65-74**: 1/2 position (2.5-3.5%)
- **60-64**: 1/4 position (1-2%)

### When to Exit
- ✓ Hit profit target
- ✓ Stop loss triggered
- ✓ Scanner generates sell signal
- ✓ SPY enters Phase 3/4
- ✓ Stock breaks below 50 SMA on volume

### Stop Management
1. Start with scanner stop loss
2. Move to breakeven after +10% gain
3. Trail stop to 50 SMA or swing lows
4. Exit if no progress after 3-4 weeks

---

That's it. Track every trade. 13 columns is all you need.
