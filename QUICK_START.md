# Quick Start Guide - Quant Analysis Engine

> This guide covers the `config.yaml` / `run_screen.sh` workflow (the earlier
> "quant engine" scanner, `scripts/run_quant_engine.py`). For the main
> full-market scanner used by the daily GitHub Actions automation, see the
> [top-level README](README.md#quick-start) instead.

## Common Setup Issue: `ModuleNotFoundError`

If you see `ModuleNotFoundError: No module named 'numpy'` (or any other
dependency), it's because you're using the system Python instead of the
project's virtual environment where dependencies are installed.

## Solution: Always Use the Virtual Environment

You have **two options** to run the system:

### Option 1: Use the Convenience Scripts (EASIEST)

I've created shell scripts that automatically activate the virtual environment:

```bash
# Run quick test (5 stocks)
./run_test.sh

# Run full screening
./run_screen.sh

# Run with custom tickers
./run_screen.sh --tickers AAPL MSFT GOOGL
```

### Option 2: Manually Activate Virtual Environment

```bash
# Activate virtual environment first
source venv/bin/activate

# Then run any Python script
python test_quant_engine.py
python run_quant_engine.py
python run_quant_engine.py --tickers AAPL MSFT

# Deactivate when done (optional)
deactivate
```

## Why This Happens

- **System Python**: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python`
  - This is macOS's global Python installation
  - Doesn't have project dependencies installed

- **Virtual Environment Python**: `./venv/bin/python`
  - Project-specific Python with all dependencies installed
  - Isolated from system Python
  - Contains numpy, pandas, yfinance, etc.

## Recommended Workflow

### Daily Screening

```bash
# Navigate to project directory (wherever you cloned it)
cd /path/to/stock-screener

# Run screening (uses virtual environment automatically)
./run_screen.sh
```

The results will be saved to `./data/results/quant_screen_YYYYMMDD_HHMMSS.txt`

### Quick Test (After Changes)

```bash
./run_test.sh
```

### Custom Ticker Lists

```bash
# Screen specific stocks
./run_screen.sh --tickers AAPL MSFT GOOGL NVDA AMD TSLA META

# Don't save results to file
./run_screen.sh --no-save

# Use custom config
./run_screen.sh --config my_config.yaml
```

## Installation Check

If you need to verify/reinstall dependencies:

```bash
# Activate virtual environment
source venv/bin/activate

# Install/update all dependencies
pip install -r requirements.txt

# Verify installation
python -c "import numpy, pandas, yfinance, yaml; print('All dependencies installed!')"
```

## Common Commands

```bash
# Quick test (recommended first run)
./run_test.sh

# Full screening with default config
./run_screen.sh

# Screen with custom tickers
./run_screen.sh --tickers AAPL MSFT GOOGL

# View help
./run_screen.sh --help

# Clear cache (force fresh data)
source venv/bin/activate
python -c "from src.data.fetcher import YahooFinanceFetcher; YahooFinanceFetcher().clear_cache()"
```

## What Each File Does

| File | Purpose |
|------|---------|
| `run_test.sh` | Quick test with 5 stocks (uses venv automatically) |
| `run_screen.sh` | Full screening (uses venv automatically) |
| `test_quant_engine.py` | Python test script |
| `run_quant_engine.py` | Python main script |
| `config.yaml` | Stock universe and parameters |

## Troubleshooting

### Issue: "No module named 'xxx'"

**Solution**: You forgot to activate the virtual environment or use the shell scripts.

```bash
# Use the shell script (easiest)
./run_test.sh

# OR activate venv manually
source venv/bin/activate
python test_quant_engine.py
```

### Issue: "Permission denied: ./run_test.sh"

**Solution**: Make the script executable.

```bash
chmod +x run_test.sh run_screen.sh
./run_test.sh
```

### Issue: "Insufficient data" or "Failed to fetch"

**Solution**: Either network issue or invalid ticker. Check:
- Internet connection
- Ticker symbols are valid
- Yahoo Finance is accessible

### Issue: Cache is stale

**Solution**: Clear cache to fetch fresh data.

```bash
source venv/bin/activate
python -c "from src.data.fetcher import YahooFinanceFetcher; YahooFinanceFetcher().clear_cache()"
```

## Editing the Stock Universe

Edit `config.yaml`:

```yaml
stock_universe:
  # Tech
  - AAPL
  - MSFT
  - GOOGL
  - META
  - NVDA

  # Add your own tickers here
  - YOUR_TICKER_1
  - YOUR_TICKER_2
```

Then run:

```bash
./run_screen.sh
```

## Output Files

Results are saved to: `./data/results/quant_screen_YYYYMMDD_HHMMSS.txt`

Example: `./data/results/quant_screen_20251126_140530.txt`

## Next Steps

1. **First run**: `./run_test.sh` (quick test with 5 stocks)
2. **Review output**: Check benchmark summary, buy/sell lists
3. **Customize**: Edit `config.yaml` to add your watchlist
4. **Daily screening**: `./run_screen.sh` (run after market close)
5. **Review results**: Check `./data/results/` folder

## Summary

✅ **Always use**: `./run_test.sh` or `./run_screen.sh`
✅ **Or activate venv first**: `source venv/bin/activate`
❌ **Don't use**: `python test_quant_engine.py` (without venv)

The shell scripts handle everything automatically - they're the easiest way to run the system!
