"""LLM evaluation harness.

Manual script (NOT part of automated pytest). Run once per release to evaluate
LLM output quality across all modules.

Run with:
    python tests/eval_llm.py

Requires HF_TOKEN in environment or .streamlit/secrets.toml.

See docs/PRD.md section 14 and docs/METHODOLOGY.md section 6.10.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.humanizer import humanize
from utils.llm import (
    LLMClient,
    LLMUnavailableError,
    get_hf_token,
    get_llm_config,
    extract_numbers,
    verify_grounding,
)
from utils.prompts import (
    build_kalkyl_explanation_prompt,
    build_investering_explanation_prompt,
    build_budget_consistency_prompt,
    build_standardkost_interpretation_prompt,
)


# ---------------------------------------------------------------------------
# Load fixtures
# ---------------------------------------------------------------------------

FIXTURES_PATH = Path(__file__).resolve().parent / "eval_fixtures.json"


def load_fixtures() -> dict:
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Prompt builders per module
# ---------------------------------------------------------------------------


def _build_prompt_for_fixture(module: str, fixture: dict) -> tuple[str, str]:
    """Build the appropriate prompt for a given module and fixture."""
    if module == "kalkyl":
        return build_kalkyl_explanation_prompt(
            fixture["calc_type"], fixture["inputs"], fixture["outputs"]
        )
    elif module == "investering":
        return build_investering_explanation_prompt(
            fixture["method"], fixture["inputs"], fixture["outputs"]
        )
    elif module == "budget":
        return build_budget_consistency_prompt(
            fixture["inputs"],
            fixture.get("outputs", {}),
            fixture.get("outputs", {}),
            fixture["outputs"].get("balanserad", True),
            0.0,
        )
    elif module == "standardkost":
        component = {
            "typ": "Rorlig kostnad",
            **{k: v for k, v in fixture["outputs"].items()},
        }
        return build_standardkost_interpretation_prompt([component])
    else:
        raise ValueError(f"Unknown module: {module}")


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

from utils.prompts import TUTOR_REQUIRED_SECTIONS as REQUIRED_SECTIONS

# Swedish character pattern - check for suspiciously many English-only words
SWEDISH_CHARS = re.compile(r"[åäöÅÄÖ]")
ENGLISH_SUSPICIOUS = re.compile(
    r"\b(the|is|are|this|that|which|however|therefore|furthermore|moreover|"
    r"consequently|additionally|specifically|particularly|essentially|"
    r"investment|calculation|company|profit|revenue|cost)\b",
    re.IGNORECASE,
)


def score_output(
    text: str, expected_numbers: dict[str, float]
) -> dict:
    """Score a single LLM output on multiple dimensions."""
    # 1. Humanizer pass
    h = humanize(text, required_sections=REQUIRED_SECTIONS)

    # 2. Grounding verification
    numeric_expected = {
        k: v for k, v in expected_numbers.items() if isinstance(v, (int, float))
    }
    grounding = verify_grounding(h.text, numeric_expected) if numeric_expected else {
        "matched": [], "missing": [], "wrong": []
    }
    total_expected = len(numeric_expected)
    matched = len(grounding["matched"])
    grounding_pct = (matched / total_expected * 100) if total_expected > 0 else 100.0

    # 3. Swedish quality heuristic
    suspicious_english = ENGLISH_SUSPICIOUS.findall(h.text)
    has_swedish_chars = bool(SWEDISH_CHARS.search(h.text))

    # 4. Word count
    word_count = len(h.text.split())

    return {
        "structure_valid": h.structure_valid,
        "missing_sections": h.missing_sections,
        "tells_found": len(h.tells_found),
        "tells_list": h.tells_found,
        "grounding_match_pct": round(grounding_pct, 1),
        "grounding_matched": grounding["matched"],
        "grounding_missing": grounding["missing"],
        "grounding_wrong": grounding["wrong"],
        "english_words_found": len(suspicious_english),
        "english_words_list": list(set(suspicious_english)),
        "has_swedish_chars": has_swedish_chars,
        "word_count": word_count,
        "cleaned_text": h.text[:500],
    }


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------


def run_evaluation(verbose: bool = True) -> dict:
    """Run the full evaluation across all modules."""
    token = get_hf_token()
    if not token:
        print("ERROR: No HF_TOKEN found. Set HF_TOKEN env var or .streamlit/secrets.toml.")
        sys.exit(1)

    config = get_llm_config()
    client = LLMClient(
        token=token,
        model=config["model"],
        provider=config["provider"],
        timeout=60,
    )

    fixtures = load_fixtures()
    modules = ["kalkyl", "investering", "budget", "standardkost"]

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": config["model"],
        "provider": config["provider"],
        "modules": {},
        "summary": {},
    }

    total_prompts = 0
    total_success = 0
    total_structure_valid = 0
    total_tells = 0
    total_grounding_sum = 0.0
    total_english_words = 0

    for module in modules:
        module_fixtures = fixtures.get(module, [])
        if not module_fixtures:
            print(f"  SKIP {module}: no fixtures")
            continue

        print(f"\n{'='*60}")
        print(f"  MODULE: {module.upper()} ({len(module_fixtures)} prompts)")
        print(f"{'='*60}")

        module_results = []

        for i, fixture in enumerate(module_fixtures):
            total_prompts += 1
            label = f"  [{i+1}/{len(module_fixtures)}]"

            try:
                sys_p, usr_p = _build_prompt_for_fixture(module, fixture)

                start = time.time()
                raw_response = client.chat(sys_p, usr_p, max_new_tokens=800, temperature=0.4)
                elapsed = time.time() - start

                score = score_output(raw_response, fixture["outputs"])
                score["latency_s"] = round(elapsed, 2)
                score["error"] = None
                total_success += 1

                if score["structure_valid"]:
                    total_structure_valid += 1
                total_tells += score["tells_found"]
                total_grounding_sum += score["grounding_match_pct"]
                total_english_words += score["english_words_found"]

                if verbose:
                    status = "OK" if score["structure_valid"] and score["tells_found"] == 0 else "WARN"
                    print(
                        f"{label} {status} | struct={score['structure_valid']} "
                        f"tells={score['tells_found']} "
                        f"ground={score['grounding_match_pct']}% "
                        f"eng={score['english_words_found']} "
                        f"words={score['word_count']} "
                        f"lat={score['latency_s']}s"
                    )

            except LLMUnavailableError as e:
                score = {"error": str(e), "latency_s": 0}
                if verbose:
                    print(f"{label} ERROR: {e}")
            except Exception as e:
                score = {"error": str(e), "latency_s": 0}
                if verbose:
                    print(f"{label} ERROR: {e}")

            module_results.append(score)

        results["modules"][module] = module_results

    # Summary
    results["summary"] = {
        "total_prompts": total_prompts,
        "total_success": total_success,
        "total_errors": total_prompts - total_success,
        "structure_valid_count": total_structure_valid,
        "structure_valid_pct": round(total_structure_valid / max(total_success, 1) * 100, 1),
        "avg_grounding_pct": round(total_grounding_sum / max(total_success, 1), 1),
        "total_tells_found": total_tells,
        "total_english_words": total_english_words,
    }

    return results


def print_summary(results: dict) -> None:
    """Print a formatted summary table."""
    s = results["summary"]
    print(f"\n{'='*60}")
    print("  EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Model:            {results['model']}")
    print(f"  Timestamp:        {results['timestamp']}")
    print(f"  Total prompts:    {s['total_prompts']}")
    print(f"  Successful:       {s['total_success']}")
    print(f"  Errors:           {s['total_errors']}")
    print(f"  Structure valid:  {s['structure_valid_count']} ({s['structure_valid_pct']}%)")
    print(f"  Avg grounding:    {s['avg_grounding_pct']}%")
    print(f"  AI tells found:   {s['total_tells_found']}")
    print(f"  English words:    {s['total_english_words']}")
    print(f"{'='*60}")

    # Per-module breakdown
    for module, mod_results in results["modules"].items():
        successes = [r for r in mod_results if r.get("error") is None]
        struct_ok = sum(1 for r in successes if r.get("structure_valid"))
        avg_ground = (
            sum(r.get("grounding_match_pct", 0) for r in successes) / max(len(successes), 1)
        )
        tells = sum(r.get("tells_found", 0) for r in successes)
        print(f"  {module:20s}  ok={len(successes)}/{len(mod_results)}  "
              f"struct={struct_ok}  ground={avg_ground:.0f}%  tells={tells}")


def print_random_samples(results: dict, n_per_module: int = 3) -> None:
    """Print random sample outputs for human review."""
    print(f"\n{'='*60}")
    print(f"  RANDOM SAMPLES ({n_per_module} per module)")
    print(f"{'='*60}")

    for module, mod_results in results["modules"].items():
        successes = [r for r in mod_results if r.get("error") is None and r.get("cleaned_text")]
        samples = random.sample(successes, min(n_per_module, len(successes)))

        for i, sample in enumerate(samples):
            print(f"\n--- {module.upper()} sample {i+1} ---")
            print(f"  Structure: {sample.get('structure_valid')}")
            print(f"  Tells: {sample.get('tells_list', [])}")
            print(f"  English: {sample.get('english_words_list', [])}")
            print(f"  Text (first 500 chars):")
            print(f"  {sample.get('cleaned_text', '(empty)')}")
            print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("LLM Evaluation Harness")
    print(f"Project: Ekonomistyrning Sandbox")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    results = run_evaluation(verbose=True)
    print_summary(results)
    print_random_samples(results, n_per_module=3)

    # Write JSON report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(__file__).resolve().parent / f"eval_results_{timestamp}.json"

    # Remove cleaned_text from JSON output to keep it compact (it was for display only)
    json_results = json.loads(json.dumps(results, default=str))
    for mod_results in json_results.get("modules", {}).values():
        for r in mod_results:
            r.pop("cleaned_text", None)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False)

    print(f"\nResults written to: {output_path}")
