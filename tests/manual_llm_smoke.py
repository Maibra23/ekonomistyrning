"""Manual LLM integration smoke test.

NOT part of automated pytest. Run only when verifying real API connectivity.

Run with:
    python tests/manual_llm_smoke.py

Requires HF_TOKEN set in environment or .streamlit/secrets.toml.
You can also place it in a .env file at the project root and load it
with python-dotenv or export it manually before running.

Usage with .env file:
    # On Linux/Mac:
    export $(grep -v '^#' .env | xargs) && python tests/manual_llm_smoke.py

    # On Windows (PowerShell):
    Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
    python tests/manual_llm_smoke.py
"""
from __future__ import annotations

import os
import sys

# Add project root to path so imports work when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass


def main() -> None:
    from utils.humanizer import humanize
    from utils.llm import (
        LLMClient,
        LLMUnavailableError,
        get_hf_token,
        get_llm_config,
        verify_grounding,
    )
    from utils.prompts import build_kalkyl_explanation_prompt

    print("=" * 60)
    print("LLM Smoke Test")
    print("=" * 60)

    # Check token
    token = get_hf_token()
    if not token:
        print("\nERROR: HF_TOKEN not found.")
        print("Set it via:")
        print("  - .env file in project root")
        print("  - .streamlit/secrets.toml")
        print("  - HF_TOKEN environment variable")
        sys.exit(1)

    print(f"\nToken found: {token[:8]}...")

    # Load config
    config = get_llm_config()
    print(f"Model: {config.model}")
    print(f"Provider: {config.provider}")

    # Build a kalkyl explanation prompt using a small example
    inputs = {
        "direkt_material": 850,
        "direkt_lon": 320,
        "mo_pct": 25,
        "to_pct": 80,
        "ao_pct": 12,
        "fo_pct": 8,
        "units": 5000,
    }
    outputs = {
        "materialomkostnad": 212.5,
        "tillverkningsomkostnad": 256.0,
        "tillverkningskostnad": 1638.5,
        "administrationsomkostnad": 196.62,
        "forsaljningsomkostnad": 131.08,
        "sjalvkostnad_per_styck": 1966.2,
        "sjalvkostnad_totalt": 9831000.0,
    }

    system_prompt, user_prompt = build_kalkyl_explanation_prompt(
        "sjalvkostnad", inputs, outputs, scenario_name="Exempelföretag AB"
    )

    print("\n--- System Prompt (first 200 chars) ---")
    print(system_prompt[:200] + "...")
    print(f"\n--- User Prompt ({len(user_prompt)} chars) ---")
    print(user_prompt[:300] + "...")

    # Call LLM
    print("\n--- Calling LLM ---")
    try:
        client = LLMClient(token=config.token, model=config.model, provider=config.provider)
        response = client.chat(system_prompt, user_prompt)
    except LLMUnavailableError as exc:
        print(f"\nLLM UNAVAILABLE: {exc}")
        sys.exit(1)

    print(f"\nResponse length: {len(response)} chars")
    print("\n--- Raw Response ---")
    print(response)

    # Run through humanizer
    print("\n--- Humanizer Results ---")
    result = humanize(
        response,
        required_sections=["Antagande", "Beräkning", "Tolkning", "Källor och förbehåll"],
    )
    print(f"Structure valid: {result.structure_valid}")
    print(f"Missing sections: {result.missing_sections}")
    print(f"AI tells found: {result.tells_found}")
    print(f"Transformations: {result.transformations_applied}")

    if result.tells_found:
        print("\nWARNING: AI tells detected and removed.")

    # Verify grounding
    print("\n--- Grounding Verification ---")
    expected_numbers = {
        "direkt_material": 850,
        "direkt_lon": 320,
        "sjalvkostnad_per_styck": 1966.2,
    }
    grounding = verify_grounding(result.text, expected_numbers)
    print(f"Matched: {grounding['matched']}")
    print(f"Missing: {grounding['missing']}")

    print("\n--- Cleaned Response ---")
    print(result.text)

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
