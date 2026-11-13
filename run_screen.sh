#!/bin/bash
# Main screening runner. Activates ./venv if it exists, otherwise uses the current Python.

cd "$(dirname "$0")"
[ -f venv/bin/activate ] && source venv/bin/activate
python scripts/run_quant_engine.py "$@"
