"""Check that an Anthropic API key is set and works, without printing it.

    python scripts/check_api_key.py

Reports where the key was found (process / Windows user / Windows machine
environment) and its last 4 characters, then lists models (a free call) to
confirm authentication and that the calibration models are available.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spreadsheet_env.agents.policies import PRICES, api_key_source  # noqa: E402


def main():
    key, source = api_key_source()
    if not key:
        print("No ANTHROPIC_API_KEY found (process, Windows user or machine environment).")
        sys.exit(1)
    print(f"key found in: {source}  (ends with ...{key[-4:]}, length {len(key)})")
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    try:
        ids = [m.id for m in client.models.list(limit=100)]
    except anthropic.AuthenticationError:
        print("Authentication FAILED: the key is invalid or revoked.")
        sys.exit(2)
    except anthropic.APIConnectionError as e:
        print(f"Could not reach the API: {e}")
        sys.exit(3)
    print(f"authenticated; {len(ids)} models visible")
    for m in PRICES:
        print(f"  {m:20s} {'available' if m in ids else 'NOT listed'}")


if __name__ == "__main__":
    main()
