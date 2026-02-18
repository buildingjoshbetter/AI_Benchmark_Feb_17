<h1 align="center">AI Benchmark</h1>

<p align="center">
  <strong>7 models. 30 tasks. One report.</strong><br>
  Qwen 3.5 vs Claude vs Gemini - head-to-head across code, design, and research.
</p>

<p align="center">
  <a href="#results">Results</a> · <a href="#models">Models</a> · <a href="#methodology">Methodology</a> · <a href="#run-it-yourself">Run It</a> · <a href="#why">Why</a>
</p>

---

## Results

**[View the interactive report →](https://ai-benchmark-feb-17.vercel.app)**

The report includes:
- Response time and token output charts per task
- Category breakdowns (code / design / research)
- Cost analysis across all 7 models
- Full output viewer with raw text and rendered HTML toggle
- Side-by-side comparison of every model's response to every prompt

### Key Findings

| Metric | Winner |
|--------|--------|
| **Fastest responses** | Qwen 3.5 Plus (avg 45.5s) |
| **Most verbose** | Claude Sonnet 4.6 (avg 8,417 tokens) |
| **Most efficient** | Gemini 2.5 Pro (avg 60.3s, 7,123 tokens) |
| **Most thorough code** | Claude Opus 4.6 |
| **Best HTML design** | Claude Opus 4.6 (24K+ token pages) |
| **Best cost/performance** | Qwen 3.5 Plus ($0.72/M output) |

## Models

Seven models tested via [OpenRouter](https://openrouter.ai), all at `temperature=0` for reproducibility:

| Model | Output Cost ($/M tokens) | Avg Tokens | Avg Time |
|-------|--:|--:|--:|
| **Qwen 3.5 397B** (Open) | $0.72 | 5,466 | 138.6s |
| **Qwen 3.5 Plus** (Hosted) | $0.72 | 3,679 | 45.5s |
| **Claude Sonnet 4.5** | $15.00 | 5,827 | 80.9s |
| **Claude Sonnet 4.6** | $15.00 | 8,417 | 100.1s |
| **Claude Opus 4.5** | $75.00 | 6,805 | 79.1s |
| **Claude Opus 4.6** | $75.00 | 7,876 | 104.5s |
| **Gemini 2.5 Pro** | $10.00 | 7,123 | 60.3s |

## Methodology

### 30 Prompts Across 3 Categories

**Code (10 tasks)** - REST APIs, React components, state machines, CLI tools, WebSocket servers, parsers, and more. Every task requires production-quality, runnable code.

**Design (7 tasks)** - Full single-file HTML/CSS/JS pages: SaaS landing pages, analytics dashboards, navigation menus, settings panels, onboarding flows, chat interfaces, and data tables. Rendered in-browser to compare visual quality.

**Research (10 tasks)** - Deep analysis tasks: personality frameworks, technology comparisons, second-order effects, historical analysis, and more. Tests reasoning depth and structure.

### Controls

- All models receive **identical prompts** with no system messages
- `temperature=0` across the board for deterministic output
- `max_tokens=32768` for design/HTML tasks (code and research use 8192)
- Every response is timestamped with token counts and timing
- Blind evaluation files included (model names stripped)
- Total benchmark cost: **~$38** across all 189 API calls

### What This Doesn't Test

This is a single-turn, zero-shot benchmark. It doesn't test:
- Multi-turn conversation or follow-up refinement
- Tool use or function calling
- System prompt adherence
- RAG or context window utilization
- Agentic capabilities

## Repo Structure

```
├── benchmark.py           # Benchmark runner (sends prompts, saves results)
├── generate_report.py     # Generates the interactive HTML report
├── rerun_html_tasks.py    # Re-runs design tasks with higher token limits
├── analyze.py             # CLI analysis of results
├── report/
│   └── index.html         # The interactive report (7.8MB, self-contained)
├── results/
│   ├── all_results.json   # All 189 model responses with metadata
│   ├── blind_code.json    # Blind evaluation (code tasks)
│   ├── blind_design.json  # Blind evaluation (design tasks)
│   ├── blind_research.json # Blind evaluation (research tasks)
│   └── _KEY_DO_NOT_PEEK.json  # Answer key for blind evaluation
```

## Run It Yourself

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY="sk-or-..."

# Run the full benchmark (~45 min, ~$38)
python benchmark.py

# Or run a single category
python benchmark.py --category design

# Resume if interrupted
python benchmark.py --resume

# Generate the report
python generate_report.py

# Open it
python generate_report.py --serve
```

## Why

I wanted to see if Qwen 3.5, the new open-weights model that dropped February 16, 2026, could actually compete with Claude and Gemini on real tasks. Not on MMLU. Not on HumanEval. On the stuff I actually use these models for every day: writing code, designing interfaces, and researching complex topics.

The benchmarks on model cards are meaningless to me. I don't care if a model scores 92.3% on GPQA. I care if it can build me a landing page that doesn't look like it was designed in 2014, write an API that handles edge cases, and explain a concept without hallucinating.

So I wrote 30 prompts, the kind of things I'd actually send to a model, and ran all 7 models against them head-to-head. Same prompts. Same temperature. Same token limits. The report shows every response so you can judge for yourself.

No sponsored content. No cherry-picked examples. Just raw outputs.

## Built By

**[@Building_Josh](https://twitter.com/Building_Josh)**

---

<p align="center">
  <em>"The best benchmark is the one that tests what you actually use."</em>
</p>
