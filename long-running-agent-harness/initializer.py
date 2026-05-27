"""
initializer.py — Runs ONCE to bootstrap the agent harness.

Why a separate initializer?
  Real long-running agents need a clean, known starting environment.
  Mixing setup with execution logic causes non-deterministic failures.
  The initializer is the "contract" — it defines what the agent must do.

Usage:
  python initializer.py                        # static tasks
  python initializer.py --goal "Build a REST API with auth and tests"
"""

import argparse
import json
import os
import sys

import google.generativeai as genai

from utils import PROGRESS_FILE, STATE_FILE, TASKS_FILE, append_progress, save_state

# ── Static fallback tasks (used when no --goal is given) ─────────────────────
STATIC_TASKS = [
    {"task": "Set up project structure and virtual environment", "done": False, "tested": False, "priority": 1},
    {"task": "Implement database connection module with retry logic", "done": False, "tested": False, "priority": 2},
    {"task": "Build user authentication endpoint (POST /auth/login)", "done": False, "tested": False, "priority": 3},
    {"task": "Add input validation and error handling middleware", "done": False, "tested": False, "priority": 4},
    {"task": "Write integration tests for auth endpoint", "done": False, "tested": False, "priority": 5},
    {"task": "Add rate limiting to all public endpoints", "done": False, "tested": False, "priority": 6},
    {"task": "Document API with OpenAPI/Swagger spec", "done": False, "tested": False, "priority": 7},
]

INIT_SH = """\
#!/usr/bin/env bash
# init.sh — Simulates environment setup (run before agent.py in CI/CD).
# In production this would: start Docker, seed DB, export secrets, etc.

set -e

echo "[init] Creating virtual environment..."
python -m venv .venv

echo "[init] Installing dependencies..."
.venv/bin/pip install -q google-generativeai

echo "[init] Environment ready."
"""


def generate_tasks_from_goal(goal: str, api_key: str) -> list[dict]:
    """Bonus: use Gemini to decompose a user goal into structured tasks."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
You are a senior software architect. Break the following goal into 5-8 concrete,
independently executable engineering tasks ordered by dependency.

Goal: {goal}

Return ONLY a JSON array. Each element must have exactly these keys:
  "task"     : string — one clear action
  "done"     : false
  "tested"   : false
  "priority" : integer starting at 1 (1 = first to do)

No markdown, no explanation — raw JSON only.
"""
    response = model.generate_content(prompt)
    raw = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    tasks = json.loads(raw)
    # Validate shape
    for i, t in enumerate(tasks):
        assert "task" in t, f"Task {i} missing 'task' key"
        t.setdefault("done", False)
        t.setdefault("tested", False)
        t.setdefault("priority", i + 1)
    return tasks


def already_initialised() -> bool:
    return os.path.exists(TASKS_FILE)


def main():
    parser = argparse.ArgumentParser(description="Initialise the agent harness.")
    parser.add_argument("--goal", type=str, help="Natural-language goal → auto-generate tasks via Gemini")
    parser.add_argument("--api-key", type=str, default=os.getenv("GEMINI_API_KEY"), help="Gemini API key")
    parser.add_argument("--force", action="store_true", help="Re-initialise even if already set up")
    args = parser.parse_args()

    if already_initialised() and not args.force:
        print("⚠  Harness already initialised. Use --force to reset.")
        sys.exit(0)

    # ── Generate tasks ────────────────────────────────────────────────────────
    if args.goal:
        if not args.api_key:
            print("ERROR: --goal requires GEMINI_API_KEY env var or --api-key flag.")
            sys.exit(1)
        print(f"🤖 Generating tasks for goal: {args.goal!r}")
        tasks = generate_tasks_from_goal(args.goal, args.api_key)
    else:
        tasks = STATIC_TASKS

    # ── Write tasks.json (atomic) ─────────────────────────────────────────────
    tmp = TASKS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tasks, f, indent=2)
    os.replace(tmp, TASKS_FILE)
    print(f"✅ tasks.json written ({len(tasks)} tasks)")

    # ── Write progress.txt ────────────────────────────────────────────────────
    if not os.path.exists(PROGRESS_FILE) or args.force:
        open(PROGRESS_FILE, "w").close()
    append_progress("Harness initialised.")
    print("✅ progress.txt created")

    # ── Write state.json ──────────────────────────────────────────────────────
    save_state({"version": 1, "goal": args.goal or "static", "total_tasks": len(tasks)})
    print("✅ state.json created")

    # ── Write init.sh ─────────────────────────────────────────────────────────
    with open("init.sh", "w", newline="\n") as f:
        f.write(INIT_SH)
    print("✅ init.sh created")

    print("\n🚀 Harness ready. Run: python agent.py")


if __name__ == "__main__":
    main()
