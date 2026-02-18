#!/usr/bin/env python3
"""
Analyze benchmark results and generate summary report.

Usage:
    python analyze.py                    # Full report
    python analyze.py --twitter          # Twitter thread draft
    python analyze.py --render-design    # Save design outputs as HTML files for screenshot comparison
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent / "results"


def load_results():
    results_file = RESULTS_DIR / "all_results.json"
    if not results_file.exists():
        print("No results found. Run benchmark.py first.")
        return None
    return json.loads(results_file.read_text())


def load_scorecard():
    scorecard_file = RESULTS_DIR / "scorecard.json"
    if not scorecard_file.exists():
        return None
    return json.loads(scorecard_file.read_text())


def performance_summary(results):
    """Summarize token counts, speed, and cost."""
    stats = defaultdict(lambda: {"tokens_in": 0, "tokens_out": 0, "time": 0, "count": 0, "errors": 0})

    for r in results:
        key = r["model_key"]
        if r["error"]:
            stats[key]["errors"] += 1
        else:
            stats[key]["tokens_in"] += r["tokens_in"]
            stats[key]["tokens_out"] += r["tokens_out"]
            stats[key]["time"] += r["time_seconds"]
            stats[key]["count"] += 1

    print("\n" + "="*70)
    print("  PERFORMANCE SUMMARY")
    print("="*70)

    for model_key in ["qwen35", "sonnet45"]:
        s = stats[model_key]
        name = "Qwen 3.5 Plus" if model_key == "qwen35" else "Claude Sonnet 4.5"
        avg_time = s["time"] / s["count"] if s["count"] else 0
        avg_tokens = s["tokens_out"] / s["count"] if s["count"] else 0
        tok_per_sec = s["tokens_out"] / s["time"] if s["time"] else 0

        if model_key == "qwen35":
            cost = (s["tokens_in"] * 0.18 + s["tokens_out"] * 0.72) / 1_000_000
        else:
            cost = (s["tokens_in"] * 3.0 + s["tokens_out"] * 15.0) / 1_000_000

        print(f"\n  {name}:")
        print(f"    Responses:       {s['count']} ({s['errors']} errors)")
        print(f"    Total tokens:    {s['tokens_in'] + s['tokens_out']:,} ({s['tokens_in']:,} in, {s['tokens_out']:,} out)")
        print(f"    Avg response:    {avg_tokens:.0f} tokens, {avg_time:.1f}s")
        print(f"    Speed:           {tok_per_sec:.1f} tok/s")
        print(f"    Est. cost:       ${cost:.4f}")


def score_summary(scorecard):
    """Summarize scores from the scorecard."""
    if not scorecard:
        print("\n  No scorecard found. Run: python benchmark.py --scorecard")
        print("  Then fill in scores and re-run this analyzer.")
        return None

    scores = scorecard["scores"]

    # Check if any scores are filled in
    has_scores = False
    for pid, data in scores.items():
        for model in ["Model_A", "Model_B"]:
            for criterion, val in data[model].items():
                if val is not None:
                    has_scores = True
                    break

    if not has_scores:
        print("\n  Scorecard exists but no scores filled in yet.")
        print("  Edit results/scorecard.json and fill in scores (1-10).")
        return None

    print("\n" + "="*70)
    print("  QUALITY SCORES (Blind Evaluation)")
    print("="*70)

    cat_totals = defaultdict(lambda: {"Model_A": [], "Model_B": []})
    overall = {"Model_A": [], "Model_B": []}

    for pid, data in scores.items():
        cat = data["category"]
        title = data["title"]
        a_scores = [v for v in data["Model_A"].values() if v is not None]
        b_scores = [v for v in data["Model_B"].values() if v is not None]

        if a_scores and b_scores:
            a_avg = sum(a_scores) / len(a_scores)
            b_avg = sum(b_scores) / len(b_scores)
            cat_totals[cat]["Model_A"].append(a_avg)
            cat_totals[cat]["Model_B"].append(b_avg)
            overall["Model_A"].append(a_avg)
            overall["Model_B"].append(b_avg)

            winner = "A" if a_avg > b_avg else "B" if b_avg > a_avg else "TIE"
            print(f"\n  {title}")
            print(f"    Model A: {a_avg:.1f}/10  |  Model B: {b_avg:.1f}/10  →  {winner}")

    print(f"\n{'─'*70}")
    print("  CATEGORY AVERAGES:")

    category_winners = {}
    for cat in ["code", "design", "research"]:
        if cat in cat_totals:
            a = cat_totals[cat]["Model_A"]
            b = cat_totals[cat]["Model_B"]
            a_avg = sum(a) / len(a) if a else 0
            b_avg = sum(b) / len(b) if b else 0
            winner = "A" if a_avg > b_avg else "B" if b_avg > a_avg else "TIE"
            category_winners[cat] = winner
            print(f"    {cat.upper():12s}  Model A: {a_avg:.1f}  |  Model B: {b_avg:.1f}  →  {winner}")

    a_overall = sum(overall["Model_A"]) / len(overall["Model_A"]) if overall["Model_A"] else 0
    b_overall = sum(overall["Model_B"]) / len(overall["Model_B"]) if overall["Model_B"] else 0
    overall_winner = "A" if a_overall > b_overall else "B" if b_overall > a_overall else "TIE"

    print(f"\n    {'OVERALL':12s}  Model A: {a_overall:.1f}  |  Model B: {b_overall:.1f}  →  {overall_winner}")

    # Reveal
    key_file = RESULTS_DIR / "_KEY_DO_NOT_PEEK.json"
    if key_file.exists():
        key = json.loads(key_file.read_text())
        print(f"\n{'─'*70}")
        print("  KEY:")
        print(f"    Model A = {key['Model_A']}")
        print(f"    Model B = {key['Model_B']}")

    return {
        "category_winners": category_winners,
        "overall_a": a_overall,
        "overall_b": b_overall,
        "overall_winner": overall_winner,
    }


def render_design_outputs(results):
    """Save design task HTML outputs for visual comparison."""
    design_dir = RESULTS_DIR / "design_renders"
    design_dir.mkdir(exist_ok=True)

    design_results = [r for r in results if r["category"] == "design" and r["response"]]

    for r in design_results:
        # Extract HTML from response (it might be in a code block)
        content = r["response"]
        if "```html" in content:
            content = content.split("```html", 1)[1]
            content = content.split("```", 1)[0]
        elif "```" in content:
            # Try to find the HTML block
            parts = content.split("```")
            for part in parts[1::2]:  # odd indices are code blocks
                if "<html" in part.lower() or "<!doctype" in part.lower() or "<div" in part:
                    content = part
                    if content.startswith("html\n"):
                        content = content[5:]
                    break

        label = "A" if r["model_key"] == "qwen35" else "B"
        filename = f"{r['prompt_id']}_{label}.html"
        filepath = design_dir / filename
        filepath.write_text(content)
        print(f"  Saved: {filepath}")

    print(f"\n  Open the HTML files in your browser to compare side-by-side.")
    print(f"  Directory: {design_dir}")


def twitter_thread(results, score_data):
    """Generate a Twitter thread draft."""
    print("\n" + "="*70)
    print("  TWITTER THREAD DRAFT")
    print("="*70)

    # Count stats
    total_prompts = len(set(r["prompt_id"] for r in results))
    qwen_results = [r for r in results if r["model_key"] == "qwen35" and not r["error"]]
    sonnet_results = [r for r in results if r["model_key"] == "sonnet45" and not r["error"]]

    qwen_cost = sum((r["tokens_in"] * 0.18 + r["tokens_out"] * 0.72) / 1_000_000 for r in qwen_results)
    sonnet_cost = sum((r["tokens_in"] * 3.0 + r["tokens_out"] * 15.0) / 1_000_000 for r in sonnet_results)

    qwen_avg_time = sum(r["time_seconds"] for r in qwen_results) / len(qwen_results) if qwen_results else 0
    sonnet_avg_time = sum(r["time_seconds"] for r in sonnet_results) / len(sonnet_results) if sonnet_results else 0

    thread = []

    thread.append(f"""1/ Just ran an independent benchmark of Alibaba's new Qwen 3.5 (397B params, 17B active MoE) against Claude Sonnet 4.5.

{total_prompts} real-world tasks across code, design, and research/reasoning.

No cherry-picking. Same prompts, temp=0, blind evaluation.

Here's what I found:""")

    if score_data:
        cw = score_data.get("category_winners", {})
        thread.append(f"""2/ CODE QUALITY (10 tasks — API auth, React components, algorithms, debugging, refactoring, SQL, tests):

Model A avg: {score_data['overall_a']:.1f}/10
Model B avg: {score_data['overall_b']:.1f}/10

Winner: Model {score_data['overall_winner']}

[screenshots of best/worst outputs]""")

    thread.append(f"""3/ COST COMPARISON:

Qwen 3.5 Plus: ${qwen_cost:.4f} total (all {total_prompts} tasks)
Claude Sonnet 4.5: ${sonnet_cost:.4f} total

Qwen is ~{sonnet_cost/qwen_cost:.0f}x cheaper per token.

Avg response time:
Qwen: {qwen_avg_time:.1f}s
Sonnet: {sonnet_avg_time:.1f}s""")

    thread.append("""4/ METHODOLOGY:
- All prompts identical, temperature=0
- Blind-labeled (Model A / Model B)
- Scored 1-10 on 5 criteria per category
- Run via OpenRouter API
- Full results + prompts on GitHub [link]""")

    thread.append("""5/ My take:

[Fill in your honest assessment after evaluating]

Full benchmark code + results: [GitHub link]""")

    for i, tweet in enumerate(thread):
        print(f"\n{'─'*50}")
        print(tweet)
        chars = len(tweet)
        print(f"  [{chars}/280 chars]" if chars <= 280 else f"  [{chars} chars — NEEDS TRIMMING]")


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze benchmark results")
    parser.add_argument("--twitter", action="store_true", help="Generate Twitter thread draft")
    parser.add_argument("--render-design", action="store_true", help="Save design outputs as HTML")
    args = parser.parse_args()

    results = load_results()
    if not results:
        exit(1)

    if args.render_design:
        render_design_outputs(results)
    else:
        performance_summary(results)
        scorecard = load_scorecard()
        score_data = score_summary(scorecard)
        if args.twitter:
            twitter_thread(results, score_data)

    print()
