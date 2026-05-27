"""
agent.py — Long-running agent loop. Each invocation = one task.

Harness engineering principles enforced here:
  1. ALWAYS read state before acting  (no assumed memory)
  2. ALWAYS pick exactly ONE task     (incremental execution)
  3. ALWAYS validate before marking complete (no false positives)
  4. ALWAYS leave files in clean state (atomic writes via utils)
  5. ALWAYS log every action          (full audit trail)

Usage:
  python agent.py                     # run one task
  python agent.py --dry-run           # show what would happen, no API call
  python agent.py --retries 3         # retry validation up to 3 times
"""

import argparse
import os
import sys

import google.generativeai as genai

from utils import (
    append_progress,
    load_progress,
    load_state,
    load_tasks,
    pick_next_task,
    save_state,
    save_tasks,
    summarise_state,
)

MAX_RETRIES_DEFAULT = 2


# ── Gemini call ───────────────────────────────────────────────────────────────

def call_gemini(api_key: str, task: dict, progress: str, state: dict) -> str:
    """
    Behavior shaping via prompt engineering:
    The prompt explicitly forbids multi-tasking, partial work, and vague output.
    This is harness-level control — the LLM cannot deviate from the contract.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    system_context = summarise_state(load_tasks(), progress)

    prompt = f"""
You are a disciplined software engineer working inside a long-running agent harness.

## Current System State
{system_context}

## Your Assignment (ONE task only)
Task: {task['task']}
Priority: {task.get('priority', '?')}

## Strict Rules (harness-enforced)
1. Work on THIS task only — do not touch anything else.
2. Produce a complete, working implementation — no TODOs, no placeholders.
3. Leave the system in a clean state when done.
4. End your response with a one-sentence summary prefixed: SUMMARY:

## Agent Metadata
Goal: {state.get('goal', 'N/A')}
Total tasks: {state.get('total_tasks', '?')}

Now implement the task. Show your reasoning step by step, then the implementation.
"""
    response = model.generate_content(prompt)
    return response.text.strip()


# ── Validation layer ──────────────────────────────────────────────────────────

def validate_task(task: dict, llm_output: str) -> tuple[bool, str]:
    """
    Validation layer — prevents agents from falsely marking tasks complete.

    In production this would run actual tests (pytest, curl, etc.).
    Here we simulate with heuristic checks that are still meaningful:
      - LLM must have produced non-trivial output
      - Output must contain a SUMMARY line (harness contract)
      - Output must not contain known failure signals
    """
    if len(llm_output.strip()) < 100:
        return False, "Output too short — likely incomplete."

    if "SUMMARY:" not in llm_output:
        return False, "Missing SUMMARY line — agent did not follow contract."

    failure_signals = ["i cannot", "i'm unable", "error:", "traceback", "not possible"]
    lower = llm_output.lower()
    for signal in failure_signals:
        if signal in lower:
            return False, f"Failure signal detected: '{signal}'"

    return True, "Validation passed."


# ── Main agent loop ───────────────────────────────────────────────────────────

def run_agent(api_key: str, dry_run: bool, max_retries: int):
    # ── Step 1: Load state (NEVER assume memory from previous runs) ───────────
    print("── [1/6] Loading system state ──────────────────────────────────────")
    tasks = load_tasks()
    progress = load_progress()
    state = load_state()

    # ── Step 2: Get context — summarise before acting ─────────────────────────
    print("── [2/6] Context summary ───────────────────────────────────────────")
    print(summarise_state(tasks, progress))

    # ── Step 3: Pick ONE task (harness decides, not the agent) ────────────────
    print("── [3/6] Selecting task ────────────────────────────────────────────")
    task = pick_next_task(tasks)
    if task is None:
        print("🎉 All tasks complete!")
        append_progress("All tasks complete.")
        return

    print(f"  → [{task.get('priority','?')}] {task['task']}")

    if dry_run:
        print("  (dry-run mode — skipping API call)")
        return

    # ── Step 4: Call Gemini ───────────────────────────────────────────────────
    print("── [4/6] Calling Gemini ────────────────────────────────────────────")
    append_progress(f"START: {task['task']}")

    try:
        llm_output = call_gemini(api_key, task, progress, state)
    except Exception as e:
        # Clean state: log failure, do NOT mark task done
        msg = f"FAIL (API error): {task['task']} — {e}"
        append_progress(msg)
        print(f"❌ {msg}")
        sys.exit(1)

    print("\n── Agent reasoning & output ────────────────────────────────────────")
    print(llm_output)

    # ── Step 5: Validate (retry loop) ─────────────────────────────────────────
    print("\n── [5/6] Validating ────────────────────────────────────────────────")
    passed, reason = False, "Not attempted"
    for attempt in range(1, max_retries + 2):  # +2: first try + retries
        passed, reason = validate_task(task, llm_output)
        print(f"  Attempt {attempt}: {reason}")
        if passed:
            break
        if attempt <= max_retries:
            print("  ↻ Retrying with stricter prompt...")
            try:
                llm_output = call_gemini(api_key, task, progress + f"\nPrevious attempt failed: {reason}", state)
            except Exception as e:
                reason = f"API error on retry: {e}"
                break

    # ── Step 6: Update state (clean state enforcement) ────────────────────────
    print("── [6/6] Updating state ────────────────────────────────────────────")
    if passed:
        task["done"] = True
        task["tested"] = True  # only set after validation — never before
        save_tasks(tasks)

        # Extract SUMMARY line for the progress log
        summary_line = next(
            (line for line in llm_output.splitlines() if line.startswith("SUMMARY:")),
            f"SUMMARY: Completed '{task['task']}'" 
        )
        append_progress(f"DONE: {task['task']} | {summary_line}")

        # Update session counter in state
        state["sessions"] = state.get("sessions", 0) + 1
        save_state(state)

        print(f"✅ Task marked done + tested: {task['task']}")
    else:
        # Clean state: partial work is NOT committed
        append_progress(f"FAIL (validation): {task['task']} — {reason}")
        print(f"❌ Validation failed — task NOT marked complete. Reason: {reason}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run one agent task cycle.")
    parser.add_argument("--api-key", type=str, default=os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--dry-run", action="store_true", help="Skip API call, show state only")
    parser.add_argument("--retries", type=int, default=MAX_RETRIES_DEFAULT, help="Validation retry attempts")
    args = parser.parse_args()

    if not args.dry_run and not args.api_key:
        print("ERROR: GEMINI_API_KEY env var or --api-key required.")
        sys.exit(1)

    if not os.path.exists("tasks.json"):
        print("ERROR: tasks.json not found. Run: python initializer.py")
        sys.exit(1)

    run_agent(args.api_key, args.dry_run, args.retries)


if __name__ == "__main__":
    main()
