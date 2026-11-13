#!/bin/bash
# Quick test runner. Activates ./venv if it exists, otherwise uses the current Python.

cd "$(dirname "$0")"
[ -f venv/bin/activate ] && source venv/bin/activate
python tests/test_quant_engine.py
