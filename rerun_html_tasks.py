#!/usr/bin/env python3
"""
Re-run truncated HTML tasks with max_tokens=32768.
Replaces results in all_results.json for design_01–07 + code_07 across all models.
"""

import openai
import json
import time
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Reuse config from benchmark.py ──
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or ""
if not OPENROUTER_API_KEY:
    env_path = Path.home() / "Downloads" / "Trainer-main" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                OPENROUTER_API_KEY = line.split("=", 1)[1].strip()
                break

if not OPENROUTER_API_KEY:
    print("ERROR: No OPENROUTER_API_KEY found.")
    sys.exit(1)

# Import models and prompts from benchmark
sys.path.insert(0, str(Path(__file__).parent))
from benchmark import MODELS, PROMPTS

OUTPUT_DIR = Path(__file__).parent / "results"
RESULTS_FILE = OUTPUT_DIR / "all_results.json"

# Tasks to re-run (all design + code_07_websocket)
RERUN_TASKS = [
    "design_01_landing", "design_02_dashboard", "design_03_navigation",
    "design_04_settings", "design_05_onboarding", "design_06_chat",
    "design_07_data_table", "code_07_websocket",
]

NEW_MAX_TOKENS = 32768


def main():
    # Load existing results
    if not RESULTS_FILE.exists():
        print("ERROR: No all_results.json found. Run benchmark.py first.")
        sys.exit(1)

    results = json.loads(RESULTS_FILE.read_text())
    print(f"Loaded {len(results)} existing results")

    # Back up original
    backup = OUTPUT_DIR / "all_results_backup_8k.json"
    if not backup.exists():
        backup.write_text(json.dumps(results, indent=2))
        print(f"Backed up original to {backup.name}")

    # Build index of existing results for replacement
    result_index = {}
    for i, r in enumerate(results):
        key = (r["prompt_id"], r["model_key"])
        result_index[key] = i

    # Figure out what needs re-running
    pairs = [(pid, mk) for pid in RERUN_TASKS for mk in MODELS]
    total = len(pairs)
    print(f"\nRe-running {total} tasks with max_tokens={NEW_MAX_TOKENS}")
    print(f"Tasks: {', '.join(RERUN_TASKS)}")
    print(f"Models: {', '.join(MODELS.keys())}")
    print(f"{'='*60}\n")

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    total_cost = 0.0
    succeeded = 0
    failed = 0

    for i, (prompt_id, model_key) in enumerate(pairs, 1):
        prompt_data = PROMPTS[prompt_id]
        model_info = MODELS[model_key]

        print(f"[{i}/{total}] {prompt_data['title']} → {model_info['name']}", end="", flush=True)

        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model_info["id"],
                messages=[{"role": "user", "content": prompt_data["prompt"]}],
                temperature=0,
                max_tokens=NEW_MAX_TOKENS,
            )
            elapsed = time.time() - start

            usage = response.usage
            result_data = {
                "response": response.choices[0].message.content,
                "tokens_in": usage.prompt_tokens if usage else 0,
                "tokens_out": usage.completion_tokens if usage else 0,
                "time_seconds": round(elapsed, 2),
                "error": None,
            }

            # Calculate cost
            cost = (result_data["tokens_in"] * model_info.get("cost_in", 1.0) +
                    result_data["tokens_out"] * model_info.get("cost_out", 5.0)) / 1_000_000
            total_cost += cost

            finish = response.choices[0].finish_reason
            print(f"  ✓ {result_data['tokens_out']} tokens, {result_data['time_seconds']}s, ${cost:.4f}, finish={finish}")
            succeeded += 1

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            result_data = {
                "response": None,
                "tokens_in": 0,
                "tokens_out": 0,
                "time_seconds": 0,
                "error": str(e),
            }
            failed += 1

        # Build the full entry
        entry = {
            "prompt_id": prompt_id,
            "category": prompt_data["category"],
            "title": prompt_data["title"],
            "model_key": model_key,
            "model_name": model_info["name"],
            "model_id": model_info["id"],
            "prompt": prompt_data["prompt"],
            "timestamp": datetime.now().isoformat(),
            **result_data,
        }

        # Replace in results array
        key = (prompt_id, model_key)
        if key in result_index:
            results[result_index[key]] = entry
        else:
            results.append(entry)
            result_index[key] = len(results) - 1

        # Save after each result
        RESULTS_FILE.write_text(json.dumps(results, indent=2))

        # Rate limiting
        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"  DONE: {succeeded} succeeded, {failed} failed")
    print(f"  Total cost: ${total_cost:.2f}")
    print(f"  Results saved to {RESULTS_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
