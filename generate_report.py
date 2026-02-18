#!/usr/bin/env python3
"""
Generate interactive HTML benchmark report with output viewer.
Usage: python generate_report.py [--serve]
"""

import json
import html as html_mod
import argparse
import webbrowser
import re
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_DIR = Path(__file__).parent / "report"

MODEL_COLORS = {
    "qwen35_open": "#7c6aff",
    "qwen35_plus": "#a78bfa",
    "sonnet45": "#ff6a8a",
    "sonnet46": "#fb923c",
    "opus45": "#f97316",
    "opus46": "#ef4444",
    "gemini25_pro": "#4af0c0",
}

MODEL_ORDER = ["qwen35_open", "qwen35_plus", "sonnet45", "sonnet46", "opus45", "opus46", "gemini25_pro"]

PRICING = {
    "qwen35_open": (0.18, 0.72),
    "qwen35_plus": (0.18, 0.72),
    "sonnet45": (3.0, 15.0),
    "sonnet46": (3.0, 15.0),
    "opus45": (15.0, 75.0),
    "opus46": (15.0, 75.0),
    "gemini25_pro": (1.25, 10.0),
}


def load_results():
    f = RESULTS_DIR / "all_results.json"
    return json.loads(f.read_text()) if f.exists() else None


def compute_stats(results):
    models = {}
    prompts = {}
    categories = defaultdict(lambda: defaultdict(list))

    for r in results:
        mk = r["model_key"]
        mn = r["model_name"]
        cat = r["category"]
        pid = r["prompt_id"]

        if mk not in models:
            models[mk] = {"name": mn, "times": [], "tokens_out": [], "total_in": 0, "total_out": 0, "errors": 0}

        if r.get("error"):
            models[mk]["errors"] += 1
        else:
            models[mk]["times"].append(r["time_seconds"])
            models[mk]["tokens_out"].append(r["tokens_out"])
            models[mk]["total_in"] += r["tokens_in"]
            models[mk]["total_out"] += r["tokens_out"]

        if pid not in prompts:
            prompts[pid] = {"title": r["title"], "category": cat, "models": {}}
        prompts[pid]["models"][mk] = {
            "time": r.get("time_seconds", 0),
            "tokens": r.get("tokens_out", 0),
            "error": r.get("error"),
            "response": r.get("response", ""),
        }

        if not r.get("error"):
            categories[cat][mk].append({"time": r["time_seconds"], "tokens": r["tokens_out"]})

    for mk, m in models.items():
        t = m["times"]
        tok = m["tokens_out"]
        m["avg_time"] = sum(t) / len(t) if t else 0
        m["avg_tokens"] = sum(tok) / len(tok) if tok else 0
        m["tok_per_sec"] = m["total_out"] / sum(t) if sum(t) else 0
        ci, co = PRICING.get(mk, (1, 5))
        m["cost"] = (m["total_in"] * ci + m["total_out"] * co) / 1_000_000

    return {"models": models, "prompts": prompts, "categories": categories}


def extract_html_from_response(text):
    """Extract HTML content from a markdown code block."""
    if not text:
        return ""
    if "```html" in text:
        parts = text.split("```html", 1)
        if len(parts) > 1:
            code = parts[1].split("```", 1)[0]
            return code.strip()
    if "```" in text:
        blocks = re.findall(r'```(?:\w*\n)?(.*?)```', text, re.DOTALL)
        for block in blocks:
            if '<html' in block.lower() or '<!doctype' in block.lower() or ('<div' in block and 'class=' in block):
                return block.strip()
    if '<html' in text.lower() or '<!doctype' in text.lower():
        return text.strip()
    return ""


def generate_html(stats):
    models = stats["models"]
    prompts = stats["prompts"]
    categories = stats["categories"]
    active_models = [mk for mk in MODEL_ORDER if mk in models]
    n_prompts = len(prompts)
    n_models = len(active_models)
    n_total = n_prompts * n_models

    # ── Build outputs data for JS ──
    # We use base64 encoding to safely embed responses that contain HTML/JS
    import base64

    outputs_data = {}
    for pid, pdata in prompts.items():
        outputs_data[pid] = {
            "title": pdata["title"],
            "category": pdata["category"],
            "models": {}
        }
        for mk in active_models:
            pm = pdata["models"].get(mk, {})
            raw_response = pm.get("response", "") or ""
            html_content = extract_html_from_response(raw_response)
            outputs_data[pid]["models"][mk] = {
                "name": models[mk]["name"],
                "response_b64": base64.b64encode(raw_response.encode("utf-8")).decode("ascii"),
                "time": pm.get("time", 0),
                "tokens": pm.get("tokens", 0),
                "has_html": bool(html_content),
                "html_b64": base64.b64encode(html_content.encode("utf-8")).decode("ascii") if html_content else "",
            }

    # Safely encode outputs JSON for embedding — escape </script> sequences
    outputs_json_str = json.dumps(outputs_data, ensure_ascii=True)
    outputs_json_str = outputs_json_str.replace("</", "<\\/")  # prevent closing script tag

    # ── Chart data ──
    prompt_list = list(prompts.items())
    prompt_labels_js = json.dumps([p["title"][:30] for _, p in prompt_list])

    model_datasets_time = []
    model_datasets_tokens = []
    for mk in active_models:
        m = models[mk]
        color = MODEL_COLORS.get(mk, "#888")
        times = [prompts[pid]["models"].get(mk, {}).get("time", 0) for pid, _ in prompt_list]
        tokens = [prompts[pid]["models"].get(mk, {}).get("tokens", 0) for pid, _ in prompt_list]
        model_datasets_time.append({"label": m["name"], "data": times, "backgroundColor": color + "99", "borderColor": color, "borderWidth": 1, "borderRadius": 3})
        model_datasets_tokens.append({"label": m["name"], "data": tokens, "backgroundColor": color + "99", "borderColor": color, "borderWidth": 1, "borderRadius": 3})

    cat_speed = {}
    cat_tokens = {}
    for cat in ["code", "design", "research"]:
        cat_speed[cat] = {}
        cat_tokens[cat] = {}
        for mk in active_models:
            if mk in categories.get(cat, {}):
                ts = [x["time"] for x in categories[cat][mk]]
                tks = [x["tokens"] for x in categories[cat][mk]]
                cat_speed[cat][mk] = round(sum(ts) / len(ts), 1) if ts else 0
                cat_tokens[cat][mk] = round(sum(tks) / len(tks), 0) if tks else 0

    cheapest = min(active_models, key=lambda mk: models[mk].get("cost", 999))
    fastest = min(active_models, key=lambda mk: models[mk].get("avg_time", 999))
    most_verbose = max(active_models, key=lambda mk: models[mk].get("avg_tokens", 0))
    fastest_tps = max(active_models, key=lambda mk: models[mk].get("tok_per_sec", 0))

    sorted_models = sorted(active_models, key=lambda mk: models[mk]["avg_time"])

    # ── Model KPI cards ──
    model_kpi_html = ""
    for mk in sorted_models:
        m = models[mk]
        color = MODEL_COLORS.get(mk, "#888")
        model_kpi_html += f"""
        <div class="model-card" style="border-top: 3px solid {color}">
            <div class="model-name" style="color:{color}">{m["name"]}</div>
            <div class="model-stat"><span class="stat-val">{m["avg_time"]:.1f}s</span><span class="stat-label">avg response</span></div>
            <div class="model-stat"><span class="stat-val">{m["avg_tokens"]:.0f}</span><span class="stat-label">avg tokens</span></div>
            <div class="model-stat"><span class="stat-val">{m["tok_per_sec"]:.0f}/s</span><span class="stat-label">throughput</span></div>
            <div class="model-stat"><span class="stat-val">${m["cost"]:.2f}</span><span class="stat-label">total cost</span></div>
        </div>"""

    # ── Legend ──
    legend_html = "".join(f'<span><span class="legend-dot" style="background:{MODEL_COLORS.get(mk,"#888")}"></span>{models[mk]["name"]}</span>' for mk in active_models)

    # ── Tasks table ──
    model_th = "".join(f'<th colspan="2" style="color:{MODEL_COLORS.get(mk,"#888")}">{models[mk]["name"].split("(")[0].strip()}</th>' for mk in sorted_models)
    model_sub_th = '<th class="sub-th">Time</th><th class="sub-th">Tokens</th>' * len(sorted_models)

    task_rows = ""
    for pid, pdata in prompt_list:
        valid = [mk for mk in active_models if mk in pdata["models"] and not pdata["models"][mk].get("error")]
        fastest_mk = min(valid, key=lambda mk: pdata["models"][mk]["time"], default=None) if valid else None
        task_rows += f'<tr class="task-row" data-pid="{pid}" style="cursor:pointer"><td>{pdata["title"]}</td><td><span class="badge badge-{pdata["category"]}">{pdata["category"]}</span></td>'
        for mk in sorted_models:
            pm = pdata["models"].get(mk, {})
            cls = "fastest-cell" if mk == fastest_mk else ""
            task_rows += f'<td class="num {cls}">{pm.get("time",0):.1f}s</td><td class="num">{pm.get("tokens",0):,}</td>'
        task_rows += "</tr>"

    # ── Output viewer task list ──
    output_task_list = ""
    for cat in ["code", "design", "research"]:
        cat_prompts = [(pid, p) for pid, p in prompt_list if p["category"] == cat]
        output_task_list += f'<div class="output-cat-header">{cat.upper()}</div>'
        for pid, p in cat_prompts:
            output_task_list += f'<div class="output-task-item" data-pid="{pid}">{p["title"]}</div>'

    # Cost data
    total_cost = sum(m["cost"] for m in models.values())
    cost_data_js = json.dumps({mk: round(models[mk]["cost"], 4) for mk in active_models})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Model Benchmark — February 2026</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.8/dist/chart.umd.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg:#09090b; --surface:#111114; --surface2:#18181b; --surface3:#1f1f23; --border:#27272a; --text:#e4e4e7; --text-dim:#71717a; --radius:12px; }}
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased}}
        .container{{max-width:1400px;margin:0 auto;padding:0 24px}}

        header{{padding:80px 0 48px;text-align:center;border-bottom:1px solid var(--border)}}
        header h1{{font-size:3rem;font-weight:800;letter-spacing:-0.04em;background:linear-gradient(135deg,#7c6aff,#4af0c0,#ff6a8a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:16px}}
        header .subtitle{{color:var(--text-dim);font-size:1.15rem;max-width:700px;margin:0 auto 24px}}
        .meta{{display:flex;gap:32px;justify-content:center;font-size:0.85rem;color:var(--text-dim);flex-wrap:wrap}}

        nav{{position:sticky;top:0;z-index:100;background:rgba(9,9,11,0.92);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:12px 0}}
        nav .container{{display:flex;gap:4px;overflow-x:auto}}
        nav a{{color:var(--text-dim);text-decoration:none;padding:8px 16px;border-radius:8px;font-size:0.85rem;font-weight:500;white-space:nowrap;transition:all 0.2s}}
        nav a:hover{{color:var(--text);background:var(--surface2)}}

        .section{{padding:56px 0;border-bottom:1px solid var(--border)}}
        .section h2{{font-size:2rem;font-weight:700;letter-spacing:-0.02em;margin-bottom:8px}}
        .section-desc{{color:var(--text-dim);margin-bottom:36px;font-size:0.95rem}}

        .model-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:36px}}
        .model-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px}}
        .model-name{{font-size:0.85rem;font-weight:700;margin-bottom:10px}}
        .model-stat{{display:flex;justify-content:space-between;align-items:baseline;padding:3px 0}}
        .stat-val{{font-size:1rem;font-weight:700;font-variant-numeric:tabular-nums}}
        .stat-label{{font-size:0.7rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.05em}}

        .chart-container{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin:24px 0}}
        .highlight-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin:32px 0}}
        .highlight-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;text-align:center}}
        .highlight-val{{font-size:1.8rem;font-weight:800;letter-spacing:-0.03em}}
        .highlight-label{{font-size:0.8rem;color:var(--text-dim);margin-top:6px}}
        .highlight-sub{{font-size:0.75rem;color:var(--text-dim);margin-top:4px}}

        .table-wrap{{overflow-x:auto;border-radius:var(--radius);border:1px solid var(--border)}}
        table{{width:100%;border-collapse:collapse;font-size:0.8rem}}
        thead{{background:var(--surface2)}}
        th{{text-align:left;padding:10px 12px;font-weight:600;color:var(--text-dim);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.05em}}
        .sub-th{{font-size:0.65rem;color:var(--text-dim);padding:4px 12px;border-top:1px solid var(--border)}}
        td{{padding:10px 12px;border-top:1px solid var(--border);white-space:nowrap}}
        td.num{{font-variant-numeric:tabular-nums;font-weight:500}}
        tr:hover{{background:var(--surface)}}
        .fastest-cell{{color:#4af0c0;font-weight:700}}
        .task-row:hover{{background:var(--surface2) !important}}

        .badge{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.7rem;font-weight:600;text-transform:uppercase}}
        .badge-code{{background:rgba(74,240,192,0.15);color:#4af0c0}}
        .badge-design{{background:rgba(124,106,255,0.15);color:#7c6aff}}
        .badge-research{{background:rgba(255,200,60,0.15);color:#ffc83c}}

        .legend{{display:flex;gap:16px;justify-content:center;margin:20px 0;font-size:0.8rem;flex-wrap:wrap}}
        .legend-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle}}

        .method-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
        .method-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px}}
        .method-card h4{{font-size:0.9rem;margin-bottom:8px;color:#4af0c0}}
        .method-card p{{font-size:0.85rem;color:var(--text-dim);line-height:1.5}}

        /* ── Output Viewer ── */
        .output-viewer{{display:grid;grid-template-columns:260px 1fr;gap:0;min-height:700px;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:var(--surface)}}
        .output-sidebar{{border-right:1px solid var(--border);overflow-y:auto;max-height:800px;background:var(--surface2)}}
        .output-cat-header{{padding:12px 16px;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--text-dim);background:var(--bg);position:sticky;top:0}}
        .output-task-item{{padding:10px 16px;font-size:0.82rem;cursor:pointer;transition:background 0.15s;border-bottom:1px solid var(--border)}}
        .output-task-item:hover{{background:var(--surface3)}}
        .output-task-item.active{{background:var(--surface3);color:#4af0c0;font-weight:600}}
        .output-main{{overflow:hidden;display:flex;flex-direction:column}}
        .output-tabs{{display:flex;gap:0;border-bottom:1px solid var(--border);overflow-x:auto;flex-shrink:0;background:var(--surface2)}}
        .output-tab{{padding:10px 18px;font-size:0.8rem;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:all 0.15s;white-space:nowrap;color:var(--text-dim)}}
        .output-tab:hover{{color:var(--text);background:var(--surface3)}}
        .output-tab.active{{border-bottom-color:currentColor;font-weight:700}}
        .output-meta{{display:flex;gap:16px;padding:10px 20px;font-size:0.75rem;color:var(--text-dim);border-bottom:1px solid var(--border);background:var(--bg)}}
        .output-content{{flex:1;overflow-y:auto;max-height:650px}}
        .output-text{{padding:20px;font-family:'JetBrains Mono',monospace;font-size:0.82rem;line-height:1.7;white-space:pre-wrap;word-wrap:break-word}}
        .output-iframe-wrap{{width:100%;height:100%;min-height:600px;background:#fff}}
        .output-iframe-wrap iframe{{width:100%;height:100%;min-height:600px;border:0}}
        .output-toggle{{display:flex;gap:8px;padding:8px 20px;border-bottom:1px solid var(--border);background:var(--bg)}}
        .toggle-btn{{padding:4px 12px;font-size:0.72rem;border-radius:6px;cursor:pointer;border:1px solid var(--border);background:var(--surface);color:var(--text-dim);transition:all 0.15s}}
        .toggle-btn.active{{background:var(--surface3);color:var(--text);border-color:#4af0c0}}
        .output-placeholder{{display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-dim);font-size:0.95rem}}
        @media(max-width:900px){{.output-viewer{{grid-template-columns:1fr}}.output-sidebar{{max-height:200px}}}}

        footer{{padding:48px 0;text-align:center;color:var(--text-dim);font-size:0.85rem}}
        footer a{{color:#4af0c0;text-decoration:none}}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>AI Model Benchmark</h1>
        <p class="subtitle">Independent head-to-head comparison of {n_models} frontier models across {n_prompts} real-world tasks in code generation, UI design, and research reasoning.</p>
        <div class="meta">
            <span>February 17, 2026</span>
            <span>{n_prompts} Tasks</span>
            <span>{n_models} Models</span>
            <span>{n_total} API Calls</span>
            <span>Temp = 0</span>
        </div>
    </header>
</div>
<nav><div class="container">
    <a href="#models">Models</a>
    <a href="#outputs">Outputs</a>
    <a href="#speed">Speed</a>
    <a href="#cost">Cost</a>
    <a href="#verbosity">Verbosity</a>
    <a href="#tasks">All Tasks</a>
    <a href="#methodology">Methodology</a>
</div></nav>
<div class="container">

<section id="models" class="section">
    <h2>At a Glance</h2>
    <p class="section-desc">Performance across all {n_prompts} tasks. Sorted by average response time.</p>
    <div class="legend">{legend_html}</div>
    <div class="model-grid">{model_kpi_html}</div>
    <div class="highlight-grid">
        <div class="highlight-card"><div class="highlight-val" style="color:#4af0c0">{models[fastest]["name"].split("(")[0].strip()}</div><div class="highlight-label">Fastest Avg Response</div><div class="highlight-sub">{models[fastest]["avg_time"]:.1f}s per task</div></div>
        <div class="highlight-card"><div class="highlight-val" style="color:#4af0c0">{models[fastest_tps]["name"].split("(")[0].strip()}</div><div class="highlight-label">Highest Throughput</div><div class="highlight-sub">{models[fastest_tps]["tok_per_sec"]:.0f} tok/s</div></div>
        <div class="highlight-card"><div class="highlight-val" style="color:#4af0c0">{models[cheapest]["name"].split("(")[0].strip()}</div><div class="highlight-label">Lowest Cost</div><div class="highlight-sub">${models[cheapest]["cost"]:.4f} total</div></div>
        <div class="highlight-card"><div class="highlight-val" style="color:#4af0c0">{models[most_verbose]["name"].split("(")[0].strip()}</div><div class="highlight-label">Most Verbose</div><div class="highlight-sub">{models[most_verbose]["avg_tokens"]:.0f} avg tokens</div></div>
    </div>
</section>

<section id="outputs" class="section">
    <h2>Model Outputs</h2>
    <p class="section-desc">Select a task from the sidebar, then click a model tab to see its raw output. Design tasks can be rendered as live HTML.</p>
    <div class="output-viewer">
        <div class="output-sidebar" id="outputSidebar">{output_task_list}</div>
        <div class="output-main" id="outputMain">
            <div class="output-tabs" id="outputTabs"></div>
            <div id="outputToggle" class="output-toggle" style="display:none"></div>
            <div id="outputMeta" class="output-meta" style="display:none"></div>
            <div class="output-content" id="outputContent">
                <div class="output-placeholder">Select a task from the sidebar to view outputs</div>
            </div>
        </div>
    </div>
</section>

<section id="speed" class="section">
    <h2>Response Speed</h2>
    <p class="section-desc">Time to complete each task (seconds). Lower is better.</p>
    <div class="chart-container"><canvas id="speedChart" height="500"></canvas></div>
    <h3 style="margin:32px 0 16px;font-size:1.2rem;color:var(--text-dim)">Average by Category</h3>
    <div class="chart-container"><canvas id="catSpeedChart" height="250"></canvas></div>
</section>

<section id="cost" class="section">
    <h2>Cost Analysis</h2>
    <p class="section-desc">Total API cost for all {n_prompts} tasks per model. OpenRouter pricing as of Feb 17, 2026.</p>
    <div class="chart-container"><canvas id="costChart" height="280"></canvas></div>
</section>

<section id="verbosity" class="section">
    <h2>Output Verbosity</h2>
    <p class="section-desc">Token output per task.</p>
    <div class="chart-container"><canvas id="tokenChart" height="500"></canvas></div>
    <h3 style="margin:32px 0 16px;font-size:1.2rem;color:var(--text-dim)">Average by Category</h3>
    <div class="chart-container"><canvas id="catTokenChart" height="250"></canvas></div>
</section>

<section id="tasks" class="section">
    <h2>All Tasks</h2>
    <p class="section-desc">Click any row to jump to its output.</p>
    <div class="table-wrap">
        <table>
            <thead><tr><th rowspan="2">Task</th><th rowspan="2">Cat</th>{model_th}</tr><tr>{model_sub_th}</tr></thead>
            <tbody>{task_rows}</tbody>
        </table>
    </div>
</section>

<section id="methodology" class="section">
    <h2>Methodology</h2>
    <p class="section-desc">How this benchmark was conducted.</p>
    <div class="method-grid">
        <div class="method-card"><h4>Models</h4><p>{"<br>".join(f"<strong>{models[mk]['name']}</strong>" for mk in active_models)}</p></div>
        <div class="method-card"><h4>Setup</h4><p>All via OpenRouter API. Temp=0. Max 8192 tokens. No system prompt. Identical prompts.</p></div>
        <div class="method-card"><h4>Tasks</h4><p><strong>10 Code</strong>: APIs, algorithms, debugging, refactoring, SQL, WebSockets, CLI, tests, async.<br><strong>7 Design</strong>: Landing pages, dashboards, nav, settings, onboarding, chat, tables.<br><strong>10 Research</strong>: Analysis, reasoning, critique, experiment design, inference.</p></div>
        <div class="method-card"><h4>Reproducibility</h4><p>{n_total} API calls, zero errors. All raw outputs saved. Checkpoint system for resumable runs. Full code on GitHub.</p></div>
    </div>
</section>

</div>
<footer><div class="container">
    <p>Independent benchmark by <a href="https://twitter.com/buildingjoshbetter">@buildingjoshbetter</a> &mdash; February 17, 2026</p>
    <p>{n_models} models via <a href="https://openrouter.ai">OpenRouter</a> | Total cost: ${total_cost:.2f}</p>
</div></footer>

<script>
""" + "Chart.defaults.color='#71717a';Chart.defaults.borderColor='#27272a';Chart.defaults.font.family='Inter,system-ui,sans-serif';\n" \
    + f"const labels={prompt_labels_js};\n" \
    + f"const speedDS={json.dumps(model_datasets_time)};\n" \
    + f"const tokenDS={json.dumps(model_datasets_tokens)};\n" \
    + f"const catSpeedData={json.dumps(cat_speed)};\n" \
    + f"const catTokenData={json.dumps(cat_tokens)};\n" \
    + f"const modelOrder={json.dumps(active_models)};\n" \
    + f"const modelColors={json.dumps(MODEL_COLORS)};\n" \
    + f"const modelNames={json.dumps({mk:models[mk]['name'] for mk in active_models})};\n" \
    + f"const costData={cost_data_js};\n" \
    + f"const outputsData={outputs_json_str};\n" \
    + f"const NUM_PROMPTS={n_prompts};\n" \
    + r"""
new Chart(document.getElementById('speedChart'),{type:'bar',data:{labels,datasets:speedDS},options:{indexAxis:'y',responsive:true,plugins:{legend:{position:'top'},title:{display:true,text:'Response Time (seconds)',padding:16}},scales:{x:{grid:{color:'#18181b'}},y:{grid:{display:false},ticks:{font:{size:11}}}}}});
new Chart(document.getElementById('catSpeedChart'),{type:'bar',data:{labels:['Code','Design','Research'],datasets:modelOrder.map(mk=>({label:modelNames[mk],data:['code','design','research'].map(c=>(catSpeedData[c]||{})[mk]||0),backgroundColor:modelColors[mk]+'99',borderColor:modelColors[mk],borderWidth:1,borderRadius:5}))},options:{responsive:true,plugins:{title:{display:true,text:'Avg Time by Category (s)'}},scales:{y:{grid:{color:'#18181b'}},x:{grid:{display:false}}}}});
new Chart(document.getElementById('tokenChart'),{type:'bar',data:{labels,datasets:tokenDS},options:{indexAxis:'y',responsive:true,plugins:{legend:{position:'top'},title:{display:true,text:'Output Tokens by Task',padding:16}},scales:{x:{grid:{color:'#18181b'}},y:{grid:{display:false},ticks:{font:{size:11}}}}}});
new Chart(document.getElementById('catTokenChart'),{type:'bar',data:{labels:['Code','Design','Research'],datasets:modelOrder.map(mk=>({label:modelNames[mk],data:['code','design','research'].map(c=>(catTokenData[c]||{})[mk]||0),backgroundColor:modelColors[mk]+'99',borderColor:modelColors[mk],borderWidth:1,borderRadius:5}))},options:{responsive:true,plugins:{title:{display:true,text:'Avg Tokens by Category'}},scales:{y:{grid:{color:'#18181b'}},x:{grid:{display:false}}}}});
new Chart(document.getElementById('costChart'),{type:'bar',data:{labels:modelOrder.map(mk=>modelNames[mk]),datasets:[{data:modelOrder.map(mk=>costData[mk]||0),backgroundColor:modelOrder.map(mk=>modelColors[mk]+'99'),borderColor:modelOrder.map(mk=>modelColors[mk]),borderWidth:2,borderRadius:6}]},options:{responsive:true,plugins:{title:{display:true,text:'Total Cost for '+NUM_PROMPTS+' Tasks ($)'},legend:{display:false}},scales:{y:{grid:{color:'#18181b'}},x:{grid:{display:false}}}}});

// ── Output Viewer Logic ──
let currentPid=null, currentMk=null, viewMode='text';

function decodeB64(b64) {
    // Decode base64 handling UTF-8 properly
    try {
        return decodeURIComponent(Array.from(atob(b64), c=>'%'+('00'+c.charCodeAt(0).toString(16)).slice(-2)).join(''));
    } catch(e) {
        return atob(b64);
    }
}

function fixTruncatedHtml(html) {
    // Close unclosed tags in truncated HTML so the browser renders what it has
    var fixed = html;
    if (fixed.toLowerCase().indexOf('</html>') === -1) {
        // Close any open style/script tags that might hide content
        if ((fixed.match(/<style/gi)||[]).length > (fixed.match(/<\/style/gi)||[]).length) fixed += '\n<\/style>';
        if ((fixed.match(/<script/gi)||[]).length > (fixed.match(/<\/script/gi)||[]).length) fixed += '\n<\/script>';
        if (fixed.toLowerCase().indexOf('</body>') === -1) fixed += '\n</body>';
        fixed += '\n</html>';
    }
    return fixed;
}

function selectTask(pid) {
    currentPid=pid;
    document.querySelectorAll('.output-task-item').forEach(el=>el.classList.toggle('active',el.dataset.pid===pid));
    const task=outputsData[pid];
    // Auto-switch to rendered view for design tasks
    if(task.category==='design') viewMode='render';
    const tabsEl=document.getElementById('outputTabs');
    tabsEl.innerHTML='';
    modelOrder.forEach(mk=>{
        if(!task.models[mk]) return;
        const tab=document.createElement('div');
        tab.className='output-tab';
        tab.textContent=task.models[mk].name;
        tab.style.color=modelColors[mk];
        tab.onclick=()=>selectModel(mk);
        tab.dataset.mk=mk;
        tabsEl.appendChild(tab);
    });
    selectModel(modelOrder[0]);
}

function selectModel(mk) {
    currentMk=mk;
    document.querySelectorAll('.output-tab').forEach(el=>el.classList.toggle('active',el.dataset.mk===mk));
    const task=outputsData[currentPid];
    const m=task.models[mk];
    const metaEl=document.getElementById('outputMeta');
    metaEl.style.display='flex';
    metaEl.innerHTML='<span>'+m.tokens.toLocaleString()+' tokens</span><span>'+m.time.toFixed(1)+'s</span><span>'+task.category+'</span>';
    const toggleEl=document.getElementById('outputToggle');
    if(m.has_html){
        toggleEl.style.display='flex';
        toggleEl.innerHTML='<div class="toggle-btn '+(viewMode==='text'?'active':'')+'" onclick="setView(\'text\')">Raw Output</div><div class="toggle-btn '+(viewMode==='render'?'active':'')+'" onclick="setView(\'render\')">Rendered HTML</div>';
    } else {
        toggleEl.style.display='none';
        viewMode='text';
    }
    renderOutput();
}

function setView(mode) {
    viewMode=mode;
    document.querySelectorAll('.toggle-btn').forEach(el=>el.classList.toggle('active', el.textContent===(mode==='text'?'Raw Output':'Rendered HTML')));
    renderOutput();
}

function renderOutput() {
    const el=document.getElementById('outputContent');
    const m=outputsData[currentPid].models[currentMk];
    if(viewMode==='render'&&m.has_html) {
        var htmlStr = decodeB64(m.html_b64);
        htmlStr = fixTruncatedHtml(htmlStr);
        el.innerHTML='<div class="output-iframe-wrap"><iframe id="renderFrame" sandbox="allow-scripts allow-same-origin"></iframe></div>';
        var frame=document.getElementById('renderFrame');
        frame.srcdoc=htmlStr;
    } else {
        var raw=decodeB64(m.response_b64);
        var escaped=raw.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        el.innerHTML='<div class="output-text">'+escaped+'</div>';
    }
}

document.querySelectorAll('.output-task-item').forEach(el=>el.onclick=()=>selectTask(el.dataset.pid));
document.querySelectorAll('.task-row').forEach(el=>el.onclick=()=>{
    const pid=el.dataset.pid;
    document.getElementById('outputs').scrollIntoView({behavior:'smooth'});
    setTimeout(()=>selectTask(pid),400);
});
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    results = load_results()
    if not results:
        print("No results."); return
    stats = compute_stats(results)
    html = generate_html(stats)
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / "index.html"
    path.write_text(html)
    print(f"Report: {path} ({len(html):,} bytes)")
    if args.serve:
        webbrowser.open(f"file://{path.absolute()}")

if __name__ == "__main__":
    main()
