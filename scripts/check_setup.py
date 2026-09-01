#!/usr/bin/env python3
"""Check which optional integrations are configured.

Usage:
    python scripts/check_setup.py

Reads the same environment variables the app reads (via .env, loaded with
python-dotenv) and reports what's set, what's missing, and whether each
missing item is required or optional.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

OPTIONAL = [
    (
        "DATABASE_URL",
        "Falls back to sqlite:///./stock_screener.db if unset - fine for local use.",
    ),
    (
        "FMP_API_KEY",
        "Enhanced quarterly fundamentals (net margins, inventory). "
        "Free tier, 250 req/day. See docs/SETUP_FMP.md.",
    ),
    (
        "EMAIL_FROM",
        "Email notifications for daily scan results. See docs/NOTIFICATIONS_SETUP.md.",
    ),
    (
        "SLACK_WEBHOOK_URL",
        "Slack notifications for daily scan results. See docs/NOTIFICATIONS_SETUP.md.",
    ),
    (
        "ROBINHOOD_USERNAME",
        "Read-only Robinhood position tracking. See docs/ROBINHOOD_SETUP.md. "
        "Password is prompted interactively for manual runs - never put "
        "ROBINHOOD_PASSWORD in a local .env file.",
    ),
]


def check(name: str, note: str) -> None:
    if os.getenv(name):
        print(f"  ✅ {name} is set")
    else:
        print(f"  ⚠️  {name} not set")
        print(f"     {note}")


def main() -> int:
    print("Stock Screener - Environment Setup Check")
    print("=" * 60)
    print("\nNothing here is required to run a scan - all integrations")
    print("are opt-in. This just shows what's configured.\n")

    print("Optional integrations:")
    for name, note in OPTIONAL:
        check(name, note)

    print("\n" + "=" * 60)
    print("Missing items above are fine to skip - see .env.example and")
    print("the linked docs/ guide if you want to turn one on.")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
