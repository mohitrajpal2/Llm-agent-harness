"""
utils.py — Shared helpers for file I/O and state management.

Design principle: All file reads/writes go through here so the rest of the
code never touches raw JSON/text directly. This is the single source of truth
for persistence, making clean-state enforcement trivial to audit.
"""

import json
import os
from datetime import datetime

from dotenv import load_dotenv

# Load .env once here — every file that imports utils gets the key automatically.
load_dotenv()

TASKS_FILE = "tasks.json"
PROGRESS_FILE = "progress.txt"
STATE_FILE = "state.json"


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_tasks() -> list[dict]:
    with open(TASKS_FILE, "r") as f:
        return json.load(f)


def save_tasks(tasks: list[dict]) -> None:
    # Write to a temp file first, then rename — prevents corruption on crash.
    tmp = TASKS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(tasks, f, indent=2)
    os.replace(tmp, TASKS_FILE)


def load_progress() -> str:
    if not os.path.exists(PROGRESS_FILE):
        return ""
    with open(PROGRESS_FILE, "r") as f:
        return f.read()


def append_progress(message: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"[{ts}] {message}\n")


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


# ── Task helpers ──────────────────────────────────────────────────────────────

def pick_next_task(tasks: list[dict]) -> dict | None:
    """
    Behavior shaping: always pick the highest-priority incomplete task.
    Priority 1 = highest. Falls back to list order if priorities are equal.
    The agent must NEVER choose arbitrarily — the harness decides.
    """
    pending = [t for t in tasks if not t.get("done")]
    if not pending:
        return None
    return min(pending, key=lambda t: t.get("priority", 99))


def summarise_state(tasks: list[dict], progress: str) -> str:
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("done"))
    tested = sum(1 for t in tasks if t.get("tested"))
    last_lines = "\n".join(progress.strip().splitlines()[-5:]) if progress else "(none)"
    return (
        f"Tasks: {done}/{total} done, {tested}/{total} validated\n"
        f"Last progress entries:\n{last_lines}"
    )
