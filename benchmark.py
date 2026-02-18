#!/usr/bin/env python3
"""
Qwen 3.5 vs Claude Sonnet 4.5 — Independent Benchmark
======================================================
Sends identical prompts to both models via OpenRouter.
Saves raw outputs for blind evaluation.

Usage:
    python benchmark.py              # Run all benchmarks
    python benchmark.py --category code      # Run only code benchmarks
    python benchmark.py --category design    # Run only design benchmarks
    python benchmark.py --category research  # Run only research benchmarks
    python benchmark.py --resume             # Resume from last checkpoint
"""

import openai
import json
import time
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or ""

# Load from Trainer .env if not in environment
if not OPENROUTER_API_KEY:
    env_path = Path.home() / "Downloads" / "Trainer-main" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                OPENROUTER_API_KEY = line.split("=", 1)[1].strip()
                break

if not OPENROUTER_API_KEY:
    print("ERROR: No OPENROUTER_API_KEY found. Set it in your environment or .env file.")
    sys.exit(1)

MODELS = {
    # ── The model being benchmarked (dropped Feb 16, 2026) ──
    "qwen35_open": {
        "id": "qwen/qwen3.5-397b-a17b",
        "name": "Qwen 3.5 397B (Open)",
        "cost_in": 0.18,    # $/M tokens
        "cost_out": 0.72,
    },
    "qwen35_plus": {
        "id": "qwen/qwen3.5-plus-02-15",
        "name": "Qwen 3.5 Plus (Hosted)",
        "cost_in": 0.18,
        "cost_out": 0.72,
    },

    # ── Anthropic lineup ──
    "sonnet45": {
        "id": "anthropic/claude-sonnet-4.5",
        "name": "Claude Sonnet 4.5",
        "cost_in": 3.0,
        "cost_out": 15.0,
    },
    "opus45": {
        "id": "anthropic/claude-opus-4.5",
        "name": "Claude Opus 4.5",
        "cost_in": 15.0,
        "cost_out": 75.0,
    },
    "opus46": {
        "id": "anthropic/claude-opus-4.6",
        "name": "Claude Opus 4.6",
        "cost_in": 15.0,
        "cost_out": 75.0,
    },

    "sonnet46": {
        "id": "anthropic/claude-sonnet-4.6",
        "name": "Claude Sonnet 4.6",
        "cost_in": 3.0,
        "cost_out": 15.0,
    },

    # ── Google's top model ──
    "gemini25_pro": {
        "id": "google/gemini-2.5-pro",
        "name": "Gemini 2.5 Pro",
        "cost_in": 1.25,
        "cost_out": 10.0,
    },
}

OUTPUT_DIR = Path(__file__).parent / "results"
CHECKPOINT_FILE = OUTPUT_DIR / "_checkpoint.json"

# ── Prompts ─────────────────────────────────────────────────────────

PROMPTS = {
    # ━━━ CODE QUALITY (10 tasks) ━━━
    "code_01_api_auth": {
        "category": "code",
        "title": "REST API with JWT Auth",
        "prompt": """Build a Python FastAPI REST API with these endpoints:
- POST /auth/register (email, password, name)
- POST /auth/login (returns JWT access + refresh tokens)
- POST /auth/refresh (refresh token → new access token)
- GET /auth/me (returns current user, requires auth)

Requirements:
- Password hashing with bcrypt
- JWT tokens with expiry (access: 15min, refresh: 7 days)
- Pydantic models for request/response validation
- Proper HTTP status codes and error responses
- In-memory user store (dict) is fine for this exercise

Return the complete, runnable code in a single file."""
    },

    "code_02_react_table": {
        "category": "code",
        "title": "React Data Table Component",
        "prompt": """Build a React TypeScript component for a data table with:
- Column sorting (click header to toggle asc/desc)
- Text search/filter across all columns
- Pagination (configurable page size: 10/25/50)
- Row selection with checkboxes (select all / individual)
- A "selected count" indicator

Use Tailwind CSS for styling. The component should accept generic typed data via props.
Include a demo with sample user data (name, email, role, status, joined date).

Return the complete code — component file + demo usage."""
    },

    "code_03_algorithm": {
        "category": "code",
        "title": "Dynamic Programming - Longest Common Subsequence",
        "prompt": """Implement three versions of the Longest Common Subsequence (LCS) algorithm in Python:

1. Naive recursive (with time complexity analysis)
2. Memoized (top-down DP)
3. Tabulated (bottom-up DP) with space optimization

For each version:
- Include type hints
- Add a brief docstring explaining the approach and complexity
- Handle edge cases (empty strings, single char, identical strings)

Then write a comparison function that times all three on input strings of length 10, 20, and 30, printing a formatted results table.

Return complete, runnable code."""
    },

    "code_04_debug": {
        "category": "code",
        "title": "Debug Broken Code",
        "prompt": """The following JavaScript code has multiple bugs. Find and fix ALL of them, explaining each bug.

```javascript
class EventEmitter {
  constructor() {
    this.listeners = {};
  }

  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
    return this;
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb != callback);
    }
  }

  emit(event, ...args) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => cb(...args));
    }
  }

  once(event, callback) {
    const wrapper = (...args) => {
      callback(...args);
      this.off(event, callback);
    };
    this.on(event, wrapper);
  }
}

// Usage that should work:
const emitter = new EventEmitter();

let count = 0;
const increment = () => count++;
const decrement = () => count--;

emitter.on('tick', increment);
emitter.on('tick', decrement);
emitter.emit('tick');
console.log(count); // Should be 0

emitter.off('tick', decrement);
emitter.emit('tick');
console.log(count); // Should be 1

// once should fire exactly once
let onceCount = 0;
emitter.once('special', () => onceCount++);
emitter.emit('special');
emitter.emit('special');
console.log(onceCount); // Should be 1

// Error: what happens with prototype pollution?
emitter.on('__proto__', () => console.log('oops'));
emitter.emit('toString');
```

Return the fixed code with inline comments explaining each bug and fix."""
    },

    "code_05_refactor": {
        "category": "code",
        "title": "Refactor Spaghetti Code",
        "prompt": """Refactor this messy Python code into clean, well-structured code. Maintain identical behavior.

```python
def process(data, t, u=None, flag=False, m="default"):
    r = []
    if t == "filter":
        for i in range(len(data)):
            if data[i]["status"] == "active":
                if u is not None:
                    if data[i]["user_id"] == u:
                        if flag:
                            data[i]["flagged"] = True
                        r.append(data[i])
                else:
                    if m == "strict":
                        if data[i]["score"] >= 80:
                            r.append(data[i])
                    elif m == "lenient":
                        if data[i]["score"] >= 50:
                            r.append(data[i])
                    else:
                        r.append(data[i])
    elif t == "transform":
        for i in range(len(data)):
            d = {}
            d["id"] = data[i]["user_id"]
            d["name"] = data[i]["first_name"] + " " + data[i]["last_name"]
            d["email"] = data[i]["email"].lower().strip()
            if data[i]["score"] >= 90:
                d["tier"] = "gold"
            elif data[i]["score"] >= 70:
                d["tier"] = "silver"
            elif data[i]["score"] >= 50:
                d["tier"] = "bronze"
            else:
                d["tier"] = "basic"
            if flag:
                d["processed_at"] = __import__('datetime').datetime.now().isoformat()
            r.append(d)
    elif t == "aggregate":
        totals = {}
        for i in range(len(data)):
            k = data[i]["department"]
            if k not in totals:
                totals[k] = {"count": 0, "total_score": 0, "active": 0}
            totals[k]["count"] += 1
            totals[k]["total_score"] += data[i]["score"]
            if data[i]["status"] == "active":
                totals[k]["active"] += 1
        for k in totals:
            totals[k]["avg_score"] = round(totals[k]["total_score"] / totals[k]["count"], 2)
        r = totals
    return r
```

Return the refactored code with a brief explanation of the changes made."""
    },

    "code_06_sql": {
        "category": "code",
        "title": "Complex SQL Queries",
        "prompt": """Given this schema:

```sql
CREATE TABLE users (id INT PRIMARY KEY, name TEXT, email TEXT, created_at TIMESTAMP);
CREATE TABLE orders (id INT PRIMARY KEY, user_id INT REFERENCES users(id), total DECIMAL, status TEXT, created_at TIMESTAMP);
CREATE TABLE order_items (id INT PRIMARY KEY, order_id INT REFERENCES orders(id), product_id INT, quantity INT, price DECIMAL);
CREATE TABLE products (id INT PRIMARY KEY, name TEXT, category TEXT, price DECIMAL, stock INT);
```

Write these queries (PostgreSQL syntax):

1. Top 10 customers by total spend in the last 90 days, including order count and avg order value
2. Products frequently bought together (co-occurrence in same order), top 20 pairs
3. Monthly revenue trend with month-over-month percentage change
4. Customers who haven't ordered in 60+ days but were previously active (3+ orders)
5. Category-level inventory value vs revenue ratio (identify overstocked categories)

Each query should be efficient and include a brief comment explaining the approach."""
    },

    "code_07_websocket": {
        "category": "code",
        "title": "WebSocket Chat Server",
        "prompt": """Build a WebSocket chat server in Node.js (no frameworks, just the 'ws' package) with:

- Multiple chat rooms (join/leave)
- User nicknames (set on connect)
- Message history (last 50 messages per room, in-memory)
- Typing indicators (broadcast to room)
- System messages (user joined/left)
- Message format: JSON with type, room, user, content, timestamp

Include a minimal HTML/JS client that connects and provides a basic chat UI.

Return the complete server code and client HTML."""
    },

    "code_08_cli": {
        "category": "code",
        "title": "CLI Tool with Argument Parsing",
        "prompt": """Build a Python CLI tool called `fstats` (file statistics) that:

Commands:
- `fstats analyze <path>` — Recursively analyze a directory:
  - File count by extension
  - Total size by extension
  - Largest 10 files
  - Duplicate files (by hash)
  - Average file age

- `fstats compare <path1> <path2>` — Compare two directories:
  - Files only in path1
  - Files only in path2
  - Modified files (same name, different content)
  - Summary stats

Features:
- `--format json|table|csv` output format flag
- `--exclude <pattern>` glob pattern to exclude
- Progress indicator for large directories
- Color output (when terminal supports it)

Use argparse (no external deps except for optional color). Return complete, runnable code."""
    },

    "code_09_tests": {
        "category": "code",
        "title": "Write Comprehensive Tests",
        "prompt": """Write comprehensive pytest tests for this Python module:

```python
from dataclasses import dataclass, field
from typing import Optional
import re

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

class UserValidator:
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def __init__(self, min_password_length: int = 8, max_name_length: int = 100):
        self.min_password_length = min_password_length
        self.max_name_length = max_name_length

    def validate_email(self, email: str) -> ValidationResult:
        errors = []
        if not email:
            errors.append("Email is required")
        elif not self.EMAIL_REGEX.match(email):
            errors.append("Invalid email format")
        elif len(email) > 254:
            errors.append("Email too long")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_password(self, password: str) -> ValidationResult:
        errors = []
        if len(password) < self.min_password_length:
            errors.append(f"Password must be at least {self.min_password_length} characters")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain an uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain a lowercase letter")
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain a digit")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_name(self, name: str) -> ValidationResult:
        errors = []
        if not name or not name.strip():
            errors.append("Name is required")
        elif len(name) > self.max_name_length:
            errors.append(f"Name must be {self.max_name_length} characters or less")
        elif re.search(r'[<>{}\\[\\]()]', name):
            errors.append("Name contains invalid characters")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_user(self, email: str, password: str, name: str) -> ValidationResult:
        results = [
            self.validate_email(email),
            self.validate_password(password),
            self.validate_name(name),
        ]
        all_errors = [e for r in results for e in r.errors]
        return ValidationResult(valid=len(all_errors) == 0, errors=all_errors)
```

Write tests covering:
- Happy paths for all methods
- Edge cases and boundary conditions
- Invalid inputs (empty, None-like, too long, special chars)
- Custom validator config (different min_password_length, max_name_length)
- Parametrized tests where appropriate

Return complete, runnable test file."""
    },

    "code_10_async": {
        "category": "code",
        "title": "Callback to Async/Await Conversion",
        "prompt": """Convert this callback-based Node.js code to modern async/await, maintaining identical behavior:

```javascript
const fs = require('fs');
const https = require('https');

function fetchUserData(userId, callback) {
    const url = `https://jsonplaceholder.typicode.com/users/${userId}`;
    https.get(url, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
            try {
                const parsed = JSON.parse(data);
                callback(null, parsed);
            } catch (e) {
                callback(new Error('Failed to parse response'));
            }
        });
    }).on('error', (e) => {
        callback(new Error(`Request failed: ${e.message}`));
    });
}

function fetchUserPosts(userId, callback) {
    const url = `https://jsonplaceholder.typicode.com/users/${userId}/posts`;
    https.get(url, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
            try {
                callback(null, JSON.parse(data));
            } catch (e) {
                callback(new Error('Failed to parse posts'));
            }
        });
    }).on('error', (e) => {
        callback(new Error(`Request failed: ${e.message}`));
    });
}

function processUsers(userIds, callback) {
    const results = [];
    let completed = 0;
    let hasError = false;

    userIds.forEach((id, index) => {
        fetchUserData(id, (err, user) => {
            if (hasError) return;
            if (err) {
                hasError = true;
                return callback(err);
            }
            fetchUserPosts(id, (err, posts) => {
                if (hasError) return;
                if (err) {
                    hasError = true;
                    return callback(err);
                }
                results[index] = {
                    ...user,
                    posts: posts,
                    postCount: posts.length
                };
                completed++;
                if (completed === userIds.length) {
                    callback(null, results);
                }
            });
        });
    });
}

function saveResults(results, filename, callback) {
    const json = JSON.stringify(results, null, 2);
    fs.writeFile(filename, json, 'utf8', (err) => {
        if (err) return callback(new Error(`Write failed: ${err.message}`));
        fs.stat(filename, (err, stats) => {
            if (err) return callback(new Error(`Stat failed: ${err.message}`));
            callback(null, { filename, size: stats.size, count: results.length });
        });
    });
}

// Main execution
processUsers([1, 2, 3, 4, 5], (err, results) => {
    if (err) {
        console.error('Processing failed:', err.message);
        process.exit(1);
    }
    console.log(`Processed ${results.length} users`);
    saveResults(results, 'users.json', (err, info) => {
        if (err) {
            console.error('Save failed:', err.message);
            process.exit(1);
        }
        console.log(`Saved ${info.count} users to ${info.filename} (${info.size} bytes)`);
    });
});
```

Requirements:
- Use async/await with proper error handling (try/catch)
- Use native fetch() or node:https with promisified wrapper
- Use fs/promises for file operations
- Maintain the parallel-then-sequential pattern (fetch all users in parallel, then posts)
- Add proper error propagation

Return the complete converted code."""
    },

    # ━━━ DESIGN / UI (7 tasks) ━━━
    "design_01_landing": {
        "category": "design",
        "title": "SaaS Landing Page",
        "prompt": """Create a complete landing page for an AI writing assistant SaaS product called "Inkwell".

Requirements:
- Hero section with headline, subheadline, CTA button, and a mockup/illustration area
- Features section (3-4 features with icons)
- Social proof section (testimonial cards)
- Pricing section (3 tiers: Free, Pro, Enterprise)
- Footer with links

Design requirements:
- Modern, clean aesthetic
- Dark theme with accent color
- Smooth scroll behavior
- Responsive (mobile + desktop)
- Subtle animations on scroll (CSS only, no JS libraries)
- Professional typography

Return a single HTML file with embedded CSS (Tailwind via CDN is fine). Make it look like a real product page, not a template."""
    },

    "design_02_dashboard": {
        "category": "design",
        "title": "Analytics Dashboard",
        "prompt": """Create an analytics dashboard page with:

- Sidebar navigation (collapsible on mobile)
- Top bar with search, notifications bell, user avatar
- KPI cards row (4 cards: Revenue, Users, Conversion Rate, Avg Session)
- Line chart placeholder (revenue over time) — use a simple SVG or CSS chart, no chart library
- Two-column layout below: recent activity feed (left) + top products table (right)
- Date range picker in the top right

Design requirements:
- Light theme, professional look
- Proper spacing and visual hierarchy
- Interactive hover states
- Responsive layout (stacks on mobile)
- Real-looking sample data

Return a single HTML file with embedded CSS. Use Tailwind via CDN."""
    },

    "design_03_navigation": {
        "category": "design",
        "title": "Mobile Navigation Menu",
        "prompt": """Create a responsive navigation system that includes:

Desktop:
- Horizontal nav bar with logo, links, dropdown menus, and CTA button
- Dropdown menus with smooth animation
- Active state indicator
- Sticky on scroll with background blur

Mobile:
- Hamburger menu button
- Full-screen slide-in menu with staggered animation
- Nested accordion submenus
- Close button and overlay

Requirements:
- Pure CSS animations (no JavaScript libraries)
- Minimal vanilla JS for toggle functionality only
- Smooth transitions everywhere
- Accessible (keyboard navigation, ARIA attributes)
- Looks polished and premium

Return a single HTML file."""
    },

    "design_04_settings": {
        "category": "design",
        "title": "Settings/Preferences Page",
        "prompt": """Create a user settings page with these sections:

1. Profile (avatar upload area, name, email, bio textarea)
2. Notifications (toggle switches for email, push, SMS, marketing)
3. Appearance (theme selector: light/dark/system, font size slider, compact mode toggle)
4. Security (change password fields, two-factor auth toggle, active sessions list)
5. Danger Zone (delete account button with confirmation)

Design requirements:
- Tab or sidebar navigation between sections
- Clean form styling with proper labels and help text
- Toggle switches that look native
- Success/error toast notification styling
- Responsive
- Subtle section dividers

Return a single HTML file with Tailwind CDN."""
    },

    "design_05_onboarding": {
        "category": "design",
        "title": "Multi-Step Onboarding Flow",
        "prompt": """Create a multi-step onboarding flow (4 steps):

Step 1: Welcome — name, role selector (dropdown), profile photo upload area
Step 2: Preferences — select interests from a grid of cards (multi-select with visual feedback)
Step 3: Connect — connect accounts (GitHub, Google, Slack) with connect/connected states
Step 4: Complete — success animation, summary of choices, "Go to Dashboard" button

Requirements:
- Progress indicator showing current step
- Smooth transitions between steps
- Back/Next buttons with proper disabled states
- Form validation visual feedback (inline errors)
- Celebration animation on completion (CSS only)
- Clean, modern, approachable design
- Responsive

Return a single HTML file with vanilla JS for step navigation. Use Tailwind CDN."""
    },

    "design_06_chat": {
        "category": "design",
        "title": "Chat Interface",
        "prompt": """Create a chat messaging interface with:

- Contact list sidebar (with online indicators, last message preview, unread badges)
- Main chat area with message bubbles (sent vs received, different colors)
- Message input area with:
  - Text input (auto-expanding textarea)
  - Attachment button
  - Emoji button (show a simple emoji picker popup)
  - Send button
- Message features:
  - Timestamps on messages
  - Read receipts (double checkmarks)
  - Typing indicator animation ("Josh is typing...")
  - Image message bubbles (use placeholder images)
- Header showing active chat contact with status

Design requirements:
- iMessage/WhatsApp level polish
- Smooth animations on new messages
- Responsive (sidebar hides on mobile, swipe to show)
- Dark theme
- Realistic sample conversation data

Return a single HTML file."""
    },

    "design_07_data_table": {
        "category": "design",
        "title": "Advanced Data Table",
        "prompt": """Create a data table UI for managing a list of 20 team members:

Features:
- Column headers: Avatar, Name, Email, Role (badge), Department, Status (active/inactive badge), Joined Date, Actions
- Sortable columns (click header)
- Search/filter bar
- Bulk actions bar (appears when rows selected)
- Pagination with page size selector
- Row hover highlight
- Action dropdown per row (Edit, Deactivate, Remove)
- Empty state design
- Loading skeleton state

Design requirements:
- Clean, professional aesthetic (think Linear or Notion)
- Proper badge/tag styling for roles and status
- Avatars with fallback initials
- Responsive (horizontal scroll on mobile with sticky first column)
- Realistic sample data

Return a single HTML file with Tailwind CDN and minimal vanilla JS."""
    },

    # ━━━ RESEARCH / REASONING (10 tasks) ━━━
    "research_01_personality": {
        "category": "research",
        "title": "Personality Cloning State of Research",
        "prompt": """Provide a comprehensive analysis of the current state of AI personality cloning research.

Cover:
1. The most significant papers/projects in personality replication (2023-2026)
2. The three biggest unsolved problems in making AI convincingly impersonate a specific individual
3. The data requirements spectrum (minimum viable data to high fidelity)
4. The gap between current capabilities and true individual-level Turing tests
5. Ethical implications and emerging regulations

For each claim, cite specific research, papers, or documented experiments. Be specific about methodologies and results, not vague generalizations."""
    },

    "research_02_anomaly": {
        "category": "research",
        "title": "Data Anomaly Analysis",
        "prompt": """Here is a dataset of daily active users (DAU) for a mobile app over 30 days:

Day 1: 12,450 | Day 2: 12,380 | Day 3: 12,520 | Day 4: 12,610 | Day 5: 11,980
Day 6: 8,200  | Day 7: 8,450  | Day 8: 12,700 | Day 9: 12,850 | Day 10: 13,100
Day 11: 13,250 | Day 12: 18,900 | Day 13: 22,300 | Day 14: 19,800 | Day 15: 15,200
Day 16: 14,100 | Day 17: 13,800 | Day 18: 13,600 | Day 19: 13,400 | Day 20: 9,100
Day 21: 8,800  | Day 22: 13,300 | Day 23: 13,500 | Day 24: 13,700 | Day 25: 13,900
Day 26: 14,100 | Day 27: 14,300 | Day 28: 9,200  | Day 29: 8,900  | Day 30: 14,500

Identify:
1. All anomalies and their likely causes
2. The underlying weekly pattern
3. What likely happened on days 12-15 (external event?)
4. The overall growth trend after removing cyclical patterns
5. A prediction for days 31-37 with confidence intervals

Show your reasoning step by step. Use statistical concepts where appropriate."""
    },

    "research_03_compare": {
        "category": "research",
        "title": "Architecture Comparison",
        "prompt": """Compare and contrast these three approaches to building a real-time collaborative document editor:

1. Operational Transformation (OT) — as used by Google Docs
2. Conflict-free Replicated Data Types (CRDTs) — as used by Figma
3. Hybrid approach — as used by Y.js

For each approach, analyze:
- Core algorithm and how conflicts are resolved
- Latency characteristics and user experience implications
- Scalability limits (users per document, document size)
- Implementation complexity and maintenance burden
- Offline support capabilities
- Real-world production examples and their experiences

Conclude with a decision framework: given specific requirements (team size, network conditions, document complexity), which approach would you recommend and why?"""
    },

    "research_04_methodology": {
        "category": "research",
        "title": "Research Methodology Critique",
        "prompt": """Read this research abstract and provide a rigorous methodological critique:

"We conducted a study examining the effect of AI tutoring on student performance. 200 college students were recruited from an introductory psychology course and randomly assigned to two groups: AI tutor (n=100) or traditional textbook (n=100). The AI tutor group used our custom chatbot for 4 weeks to study course material, while the control group studied from the standard textbook. At the end of 4 weeks, both groups took a 50-question multiple choice exam. The AI tutor group scored significantly higher (M=82.3, SD=11.2) than the textbook group (M=74.1, SD=13.5), t(198)=4.68, p<.001, d=0.66. We conclude that AI tutoring is more effective than traditional studying methods for college students."

Identify:
1. All methodological weaknesses (minimum 5)
2. Potential confounding variables
3. Threats to internal validity
4. Threats to external validity
5. What claims are actually supported by this data vs what's overclaimed
6. How you would redesign this study to address the weaknesses"""
    },

    "research_05_experiment": {
        "category": "research",
        "title": "Experiment Design",
        "prompt": """Design a rigorous experiment to test the following hypothesis:

"Fine-tuned small language models (7B parameters) produce more authentic individual personality replication in text conversations than prompted large language models (70B+ parameters)."

Your experimental design should include:
1. Specific models to test and why
2. Independent and dependent variables with operationalized definitions
3. Control conditions and confounds to account for
4. Sample size calculation with power analysis reasoning
5. Data collection methodology (what data, from whom, how much)
6. Evaluation metrics (both automated and human)
7. Statistical analysis plan
8. Limitations you'd acknowledge
9. Expected timeline and resource requirements"""
    },

    "research_06_explain": {
        "category": "research",
        "title": "Audience-Adapted Explanation",
        "prompt": """Explain how Mixture-of-Experts (MoE) language models work at three different levels:

1. For a curious 12-year-old who knows what AI chatbots are
2. For a software engineer who understands neural networks but hasn't studied MoE
3. For an ML researcher who wants the technical details

For each level:
- Use appropriate vocabulary and analogies
- Cover: what MoE is, why it's useful, how routing works, and the tradeoffs
- Include at least one concrete example
- Keep the explanation self-contained (don't reference the other levels)"""
    },

    "research_07_second_order": {
        "category": "research",
        "title": "Second-Order Effects Analysis",
        "prompt": """Analyze the second and third-order effects of the following development:

"AI systems can now convincingly replicate any individual's communication style with just 500 text messages of training data, achieving a 50%+ pass rate on individual-level Turing tests."

Structure your analysis as:
1. First-order effects (immediate, obvious consequences)
2. Second-order effects (consequences of the consequences)
3. Third-order effects (downstream ripples)
4. Who benefits and who is harmed at each level
5. What new industries/jobs/regulations this creates
6. Historical parallels (other technologies that had similar cascading effects)
7. The most surprising or counterintuitive effect you can identify"""
    },

    "research_08_logic": {
        "category": "research",
        "title": "Logical Argument Analysis",
        "prompt": """Analyze this argument for logical validity:

"Social media algorithms optimize for engagement. Content that triggers strong emotions gets more engagement. Misinformation triggers stronger emotional reactions than factual content. Therefore, social media algorithms inherently amplify misinformation over factual content. Since most people get their news from social media, this means most people are now primarily consuming misinformation. This is why public trust in institutions has declined — people are being fed lies by algorithms."

For each step in the argument chain:
1. Is the premise supported by evidence?
2. Does the conclusion follow from the premises?
3. What logical fallacies are present?
4. What's being oversimplified or omitted?
5. Steelman the argument — what's the strongest version of this claim?
6. What would you need to prove or disprove each step?"""
    },

    "research_09_inference": {
        "category": "research",
        "title": "Conflicting Data Inference",
        "prompt": """You have these conflicting data points about a SaaS company. Determine the most likely explanation:

- Revenue grew 40% YoY (from $5M to $7M ARR)
- Customer count grew 80% (from 500 to 900 customers)
- NPS dropped from 72 to 45
- Support tickets per customer doubled
- Employee count stayed flat (50 people)
- Churn rate increased from 3% to 7% monthly
- Average contract value dropped from $10,000 to $7,778
- Sales cycle shortened from 45 days to 20 days
- Marketing spend tripled
- Product releases went from monthly to quarterly

Provide:
1. The most likely narrative that explains ALL these data points simultaneously
2. Three alternative hypotheses ranked by likelihood
3. What additional data you'd want to confirm your top hypothesis
4. What this company should do in the next 90 days
5. The critical metrics they should be tracking that they're probably not"""
    },

    "research_10_lit_review": {
        "category": "research",
        "title": "Literature Review Outline",
        "prompt": """Create a detailed literature review outline for the following research question:

"How effective are parameter-efficient fine-tuning methods (LoRA, QLoRA, prefix tuning) at preserving individual writing style compared to full fine-tuning, across different model sizes?"

Your outline should include:
1. Introduction and research question framing
2. Background sections with specific subtopics to cover
3. Methodology for the review (search strategy, inclusion/exclusion criteria, databases)
4. At least 5 key themes/categories to organize findings around
5. For each theme, list 2-3 specific questions the review should answer
6. Gap analysis section structure
7. Suggested search terms and MeSH headings
8. Approximate paper count expectations per section

Make this actionable — someone should be able to take this outline and execute the review."""
    },
}

# ── Core Functions ──────────────────────────────────────────────────

def create_client():
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )


def run_prompt(client, model_id, prompt, max_retries=3):
    """Send a prompt to a model, return response + metadata."""
    for attempt in range(max_retries):
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=8192,
            )
            elapsed = time.time() - start

            usage = response.usage
            return {
                "response": response.choices[0].message.content,
                "tokens_in": usage.prompt_tokens if usage else 0,
                "tokens_out": usage.completion_tokens if usage else 0,
                "time_seconds": round(elapsed, 2),
                "error": None,
            }
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  ⚠ Error: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return {
                    "response": None,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "time_seconds": 0,
                    "error": str(e),
                }


def load_checkpoint():
    """Load completed prompt+model pairs from checkpoint."""
    if CHECKPOINT_FILE.exists():
        return set(tuple(x) for x in json.loads(CHECKPOINT_FILE.read_text()))
    return set()


def save_checkpoint(completed):
    """Save completed prompt+model pairs."""
    CHECKPOINT_FILE.write_text(json.dumps(list(completed), indent=2))


def run_benchmarks(category_filter=None, resume=False):
    """Run all benchmarks and save results."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    client = create_client()

    # Filter prompts by category
    prompts = PROMPTS
    if category_filter:
        prompts = {k: v for k, v in PROMPTS.items() if v["category"] == category_filter}

    if not prompts:
        print(f"No prompts found for category '{category_filter}'")
        return

    # Resume support
    completed = load_checkpoint() if resume else set()
    if completed:
        print(f"Resuming — {len(completed)} prompt+model pairs already completed\n")

    total_tasks = len(prompts) * len(MODELS)
    done = len(completed & {(pid, mid) for pid in prompts for mid in MODELS})
    remaining = total_tasks - done

    print(f"{'='*60}")
    print(f"  QWEN 3.5 vs CLAUDE SONNET 4.5 BENCHMARK")
    print(f"  {len(prompts)} prompts x {len(MODELS)} models = {total_tasks} tasks")
    if done > 0:
        print(f"  {done} already done, {remaining} remaining")
    print(f"{'='*60}\n")

    results = []
    # Load existing results if resuming
    results_file = OUTPUT_DIR / "all_results.json"
    if resume and results_file.exists():
        results = json.loads(results_file.read_text())

    current = done
    total_cost = {mk: 0.0 for mk in MODELS}
    start_time = time.time()

    for prompt_id, prompt_data in prompts.items():
        for model_key, model_info in MODELS.items():
            pair = (prompt_id, model_key)
            if pair in completed:
                continue

            current += 1
            elapsed_total = time.time() - start_time
            rate = current / max(elapsed_total, 1) if current > done + 1 else 0
            eta = (total_tasks - current) / rate / 60 if rate > 0 else 0

            print(f"[{current}/{total_tasks}] {prompt_data['title']} → {model_info['name']}", end="")
            if eta > 0:
                print(f"  (ETA: {eta:.0f}min)", end="")
            print()

            result = run_prompt(client, model_info["id"], prompt_data["prompt"])

            entry = {
                "prompt_id": prompt_id,
                "category": prompt_data["category"],
                "title": prompt_data["title"],
                "model_key": model_key,
                "model_name": model_info["name"],
                "model_id": model_info["id"],
                "prompt": prompt_data["prompt"],
                "timestamp": datetime.now().isoformat(),
                **result,
            }
            results.append(entry)

            # Estimate cost
            if result["error"] is None:
                cost_in = model_info.get("cost_in", 1.0)
                cost_out = model_info.get("cost_out", 5.0)
                cost = (result["tokens_in"] * cost_in + result["tokens_out"] * cost_out) / 1_000_000
                total_cost[model_key] += cost
                print(f"  ✓ {result['tokens_out']} tokens, {result['time_seconds']}s, ~${cost:.4f}")
            else:
                print(f"  ✗ ERROR: {result['error']}")

            # Save after each response
            completed.add(pair)
            save_checkpoint(completed)
            results_file.write_text(json.dumps(results, indent=2))

            # Rate limiting — be polite to the API
            time.sleep(1)

    # ── Save final outputs ──────────────────────────────────────────

    # Save per-category blind evaluation files
    for cat in ["code", "design", "research"]:
        cat_results = [r for r in results if r["category"] == cat]
        if not cat_results:
            continue

        blind = []
        model_keys = list(MODELS.keys())
        for r in cat_results:
            idx = model_keys.index(r["model_key"]) if r["model_key"] in model_keys else 0
            label = f"Model_{chr(65 + idx)}"
            blind.append({
                "prompt_id": r["prompt_id"],
                "title": r["title"],
                "model_label": label,
                "response": r["response"],
            })

        blind_file = OUTPUT_DIR / f"blind_{cat}.json"
        blind_file.write_text(json.dumps(blind, indent=2))

    # Print summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  BENCHMARK COMPLETE")
    print(f"  Total time: {elapsed/60:.1f} minutes")
    print(f"  Total prompts: {len(prompts)}")
    print(f"  Estimated cost:")
    for mk, cost in sorted(total_cost.items(), key=lambda x: x[1], reverse=True):
        name = MODELS[mk]["name"] if mk in MODELS else mk
        print(f"    {name:30s} ${cost:.4f}")
    print(f"    {'TOTAL':30s} ${sum(total_cost.values()):.4f}")
    print(f"\n  Results saved to: {OUTPUT_DIR}/")
    print(f"  - all_results.json     (raw data)")
    print(f"  - blind_code.json      (for blind eval)")
    print(f"  - blind_design.json    (for blind eval)")
    print(f"  - blind_research.json  (for blind eval)")
    print(f"{'='*60}")

    # Key mapping (don't peek until you're done evaluating!)
    key_file = OUTPUT_DIR / "_KEY_DO_NOT_PEEK.json"
    key_mapping = {}
    for i, (mk, info) in enumerate(MODELS.items()):
        label = f"Model_{chr(65 + i)}"  # A, B, C, D, E, F
        key_mapping[label] = f"{info['name']} ({info['id']})"
    key_file.write_text(json.dumps(key_mapping, indent=2))


# ── Scoring Helper ──────────────────────────────────────────────────

def generate_scorecard():
    """Generate a blank scorecard for blind evaluation."""
    results_file = OUTPUT_DIR / "all_results.json"
    if not results_file.exists():
        print("No results found. Run benchmarks first.")
        return

    results = json.loads(results_file.read_text())
    prompts_seen = {}

    for r in results:
        pid = r["prompt_id"]
        if pid not in prompts_seen:
            prompts_seen[pid] = {"title": r["title"], "category": r["category"]}

    scorecard = {
        "instructions": "Score each model 1-10 on each criterion. Do NOT look at _KEY_DO_NOT_PEEK.json until done.",
        "criteria": {
            "code": ["correctness", "code_quality", "edge_cases", "best_practices", "completeness"],
            "design": ["visual_appeal", "responsiveness", "accessibility", "component_architecture", "attention_to_detail"],
            "research": ["accuracy", "depth", "nuance", "structure", "insight"],
        },
        "scores": {}
    }

    for pid, info in prompts_seen.items():
        scorecard["scores"][pid] = {
            "title": info["title"],
            "category": info["category"],
            "Model_A": {c: None for c in scorecard["criteria"][info["category"]]},
            "Model_B": {c: None for c in scorecard["criteria"][info["category"]]},
        }

    scorecard_file = OUTPUT_DIR / "scorecard.json"
    scorecard_file.write_text(json.dumps(scorecard, indent=2))
    print(f"Scorecard generated: {scorecard_file}")
    print("Fill in scores (1-10) for each model on each criterion.")


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qwen 3.5 vs Claude Sonnet 4.5 Benchmark")
    parser.add_argument("--category", choices=["code", "design", "research"],
                        help="Run only one category")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--scorecard", action="store_true",
                        help="Generate blank scorecard for evaluation")

    args = parser.parse_args()

    if args.scorecard:
        generate_scorecard()
    else:
        run_benchmarks(category_filter=args.category, resume=args.resume)
