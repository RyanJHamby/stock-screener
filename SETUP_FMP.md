# Setting Up Financial Modeling Prep (FMP) for Enhanced Fundamentals

## Why FMP?

yfinance is limited for quarterly fundamentals. FMP provides:
- ✅ **Net margins** (not just gross)
- ✅ **Operating margins**
- ✅ **Inventory details**
- ✅ **Complete quarterly data**
- ✅ **Free tier: 250 requests/day**

## Quick Setup (5 minutes)

### 1. Get Free API Key

1. Go to: https://site.financialmodelingprep.com/
2. Click "Get your Free API Key"
3. Sign up (free, no credit card)
4. Copy your API key

### 2. Add API Key to Environment

**Option A: .env file (Recommended)**

Add to your `.env` file:

```bash
# Add this line
FMP_API_KEY=your_api_key_here
```

**Option B: Export in terminal**

```bash
export FMP_API_KEY="your_api_key_here"
```

**Option C: Add to .zshrc / .bashrc (Permanent)**

```bash
echo 'export FMP_API_KEY="your_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### 3. Test It

```bash
source venv/bin/activate

python -c "
from src.data.fmp_fetcher import FMPFetcher
fetcher = FMPFetcher()
data = fetcher.fetch_comprehensive_fundamentals('AAPL')
print(fetcher.create_enhanced_snapshot('AAPL', data))
"
```

You should see a detailed fundamental snapshot with net margins, inventory, etc!

## Usage in Your Scanner

### Option 1: Use FMP for Buy Candidates Only (Recommended)

This saves your 250/day limit:

```python
# In your screening workflow:

# 1. Screen all 3,800 stocks with yfinance (fast)
# 2. Identify ~100-200 buy candidates
# 3. Fetch detailed FMP fundamentals ONLY for buy candidates

from src.data.fmp_fetcher import FMPFetcher

fmp = FMPFetcher()  # Reads FMP_API_KEY from environment

for buy_candidate in top_buys:
    # Fetch detailed fundamentals
    fmp_data = fmp.fetch_comprehensive_fundamentals(buy_candidate['ticker'])

    # Create enhanced snapshot
    snapshot = fmp.create_enhanced_snapshot(buy_candidate['ticker'], fmp_data)

    # Add to buy signal
    buy_candidate['fundamental_snapshot'] = snapshot
```

### Option 2: Hybrid Approach

- **yfinance**: Price data, technical indicators (all stocks)
- **FMP**: Detailed fundamentals (buy candidates only)

This gives you:
- ✅ Fast screening (3,800 stocks)
- ✅ Detailed fundamentals where it matters
- ✅ Stay under 250/day limit

## What You Get with FMP

### Income Statement
```python
{
    'date': '2024-09-30',
    'revenue': 94930000000,
    'costOfRevenue': 52050000000,
    'grossProfit': 42880000000,
    'grossProfitRatio': 0.4517,  # Gross margin
    'operatingIncome': 30730000000,
    'operatingIncomeRatio': 0.3238,  # Operating margin ✅
    'netIncome': 25200000000,
    'netIncomeRatio': 0.2655,  # NET MARGIN ✅
    'eps': 1.53,
    'epsdiluted': 1.53
}
```

### Balance Sheet
```python
{
    'date': '2024-09-30',
    'cashAndCashEquivalents': 30990000000,
    'inventory': 8990000000,  # Total inventory ✅
    'totalCurrentAssets': 154320000000,
    'totalAssets': 368060000000
}
```

### Cash Flow
```python
{
    'date': '2024-09-30',
    'operatingCashFlow': 26830000000,
    'capitalExpenditure': -2440000000,
    'freeCashFlow': 24390000000
}
```

## Enhanced Snapshot Example

```
============================================================
ENHANCED FUNDAMENTAL SNAPSHOT - AAPL
============================================================

✓ Revenue: ACCELERATING ($94.93B, +6.1% QoQ)
✓ EPS: STRONG growth ($1.53, +12.5% QoQ)

Margins:
  Gross Margin:     45.2%
  Operating Margin: 32.4%
  Net Margin:       26.6% ✓ EXPANDING (+1.2pp)

Inventory:
  Total: $9.0B (9.5% of revenue)
  ✓ Drawing down (-3.2% QoQ)
  → Strong demand signal

Overall Assessment:
✓ Fundamentals SUPPORT technical breakout
============================================================
```

## Rate Limits

**Free tier**: 250 requests/day

**API calls per stock**:
- Income statement: 1 call
- Balance sheet: 1 call
- Cash flow: 1 call
- Key metrics: 1 call
- **Total**: 4 calls per stock

**Math**:
- 250 calls/day ÷ 4 calls/stock = **~60 stocks/day**
- Perfect for analyzing your top 50-60 buy signals!

**Strategy**:
1. Screen 3,800 stocks with yfinance (uses 0 FMP calls)
2. Get top 50 buy signals
3. Fetch FMP data for top 50 (uses 200 FMP calls)
4. Stay well under 250/day limit ✅

## Comparison

| Metric | yfinance | FMP |
|--------|----------|-----|
| **Net Margin** | ❌ No | ✅ Yes |
| **Operating Margin** | ❌ No | ✅ Yes |
| **Gross Margin** | ⚠️ Limited | ✅ Yes |
| **Inventory** | ⚠️ Total only | ✅ Detailed |
| **Quarterly Revenue** | ⚠️ Limited | ✅ Full history |
| **Quarterly EPS** | ⚠️ Limited | ✅ Full history |
| **API Key** | ❌ No | ✅ Free key |
| **Rate Limit** | Unclear | 250/day |
| **Cost** | Free | Free tier |

## Alternative: SEC Edgar (Also Free)

If you want **100% free** with no rate limits:

```bash
pip install sec-edgar-toolkit
```

**Pros**:
- ✅ Completely free
- ✅ Most detailed (direct from 10-Q/10-K)
- ✅ Inventory breakdown by category

**Cons**:
- ⚠️ Slower (parse XBRL)
- ⚠️ More complex

## My Recommendation

**For your use case**:

1. **Use yfinance** for initial screening (fast, 3,800 stocks)
2. **Use FMP** for top buy candidates (detailed, <60 stocks/day)
3. **Future**: Add SEC Edgar for deep dives if needed

This gives you:
- ✅ Speed (yfinance for screening)
- ✅ Detail (FMP for buy signals)
- ✅ Free (both have free tiers)
- ✅ Scalable (stays under limits)

## Sources

Based on research from:
- [Financial Modeling Prep API Documentation](https://site.financialmodelingprep.com/developer/docs)
- [Finnhub Stock APIs](https://finnhub.io/)
- [SEC Edgar Toolkit](https://github.com/stefanoamorelli/sec-edgar-toolkit)
- [SEC Edgar Official API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Top 5 Free Financial Data APIs](https://dev.to/williamsmithh/top-5-free-financial-data-apis-for-building-a-powerful-stock-portfolio-tracker-4dhj)

## Quick Start

```bash
# 1. Get free API key from https://site.financialmodelingprep.com/

# 2. Add to .env file
echo 'FMP_API_KEY=your_key_here' >> .env

# 3. Test
source venv/bin/activate
python -c "from src.data.fmp_fetcher import FMPFetcher; print(FMPFetcher().create_enhanced_snapshot('AAPL'))"

# 4. Use in your scanner (modify screening scripts to use FMP for buy signals)
```

That's it! You now have access to **net margins, operating margins, and detailed inventory data**! 📊
