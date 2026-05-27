# Long-Running Agent Harness

A production-quality minimal Python project demonstrating **Harness Engineering for Long-Running AI Agents**, inspired by Anthropic's research on reliable agentic systems.

---

## 1. The Long-Running Agent Problem

### LLM Statelessness
Every call to an LLM starts from zero. The model has no memory of previous calls, no awareness of what it already did, and no concept of "session". If you ask it to build a feature across 10 API calls, it will happily re-do work, contradict itself, or forget constraints — unless the harness prevents it.

### Context Window Limitation
Even with large context windows (100k+ tokens), you cannot dump an entire codebase + full history into every prompt. The harness must selectively inject only the relevant state — what was done, what is next, what the rules are.

---

## 2. What is Harness Engineering?

A **harness** is the system *around* the LLM that manages:

| Concern | Without Harness | With Harness |
|---|---|---|
| Memory | None | progress.txt + state.json |
| Task selection | Agent decides (unpredictable) | Harness decides (deterministic) |
| Validation | Agent self-reports | Independent validation layer |
| State integrity | Files can corrupt | Atomic writes, clean-state enforcement |
| Workflow | Ad-hoc | Structured, incremental |

The LLM is just the reasoning engine. The harness is the operating system around it.

---

## 3. Core Idea of This Project

```
initializer.py  →  creates the contract (tasks, state, environment)
agent.py        →  executes ONE task per run, enforced by harness
utils.py        →  all persistence goes through here (single source of truth)
```

- **Task tracking**: `tasks.json` is the source of truth. Each task has `done` and `tested` flags that can only be set by the harness after validation — never by the agent directly.
- **Progress logging**: `progress.txt` is an append-only audit trail. Every START, DONE, and FAIL is timestamped.
- **Incremental execution**: One task per script run. This maps directly to how real CI/CD pipelines work — atomic, observable, reversible steps.

---

## 4. Advanced Concepts

### a) Clean State Requirement

**Why partial work causes failure:**
If an agent writes half a function and crashes, the next run sees corrupted state. It may try to "continue" from a broken baseline, compounding errors. In distributed systems this is called a partial failure — the hardest class of bug to debug.

**How this project enforces clean state:**
- All file writes use a write-to-temp-then-rename pattern (`os.replace`). A crash mid-write leaves the old file intact.
- Tasks are only marked `done: true` after the full validation cycle completes.
- If validation fails, `append_progress` logs the failure but `save_tasks` is never called — the task stays pending for the next run.

```python
# utils.py — atomic write pattern
tmp = TASKS_FILE + ".tmp"
with open(tmp, "w") as f:
    json.dump(tasks, f, indent=2)
os.replace(tmp, TASKS_FILE)  # atomic on POSIX; near-atomic on Windows
```

### b) Validation Layer

**Why agents falsely mark tasks complete:**
LLMs are trained to be helpful and to appear competent. Without external checks, they will confidently say "Done!" even when the output is incomplete, incorrect, or contains placeholders. This is not hallucination — it is the model optimising for the wrong reward signal.

**How testing fixes it:**
The `validate_task()` function in `agent.py` acts as an independent judge. The agent cannot set `tested: true` — only the harness can, after validation passes. In production, this function would run `pytest`, `curl` health checks, or static analysis. Here it checks structural contracts (output length, required SUMMARY line, absence of failure signals).

```python
def validate_task(task, llm_output) -> tuple[bool, str]:
    if "SUMMARY:" not in llm_output:
        return False, "Missing SUMMARY line — agent did not follow contract."
    ...
```

### c) Environment Initialization

**Role of the initializer:**
`initializer.py` runs exactly once (guarded by `already_initialised()`). It creates the task contract, the progress log, and the environment setup script. This separation ensures the agent always starts from a known, valid state — not from whatever was left over from a previous failed run.

**Why setup matters:**
In real agentic systems, the environment (database, API keys, file structure) must be ready before the agent acts. Mixing setup with execution is a common source of non-deterministic failures. The initializer is the "pre-flight checklist".

### d) Behavior Shaping

**How we force the agent to act like a disciplined engineer:**

The harness shapes behavior at three levels:

1. **Code structure**: `pick_next_task()` in `utils.py` selects the task — the agent has no say. It cannot skip tasks, reorder them, or work on multiple at once.

2. **Prompt engineering**: The system prompt explicitly states the rules as a numbered contract. The agent is told it is inside a harness and that its output will be validated. This primes it to be precise.

3. **Post-execution enforcement**: Even if the agent ignores the rules, the harness catches it. Missing SUMMARY? Validation fails. Output too short? Validation fails. The agent cannot "cheat" its way to `done: true`.

```
Behavior shaping stack:
  Harness logic (pick_next_task, validate_task)  ← strongest
  Prompt rules (numbered contract in system prompt)
  LLM reasoning                                  ← weakest
```

---

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    AGENT HARNESS                        │
│                                                         │
│  ┌─────────────┐     ┌──────────────────────────────┐  │
│  │initializer  │────▶│  tasks.json  (task contract) │  │
│  │    .py      │     │  progress.txt (audit log)    │  │
│  │  (once)     │     │  state.json  (metadata)      │  │
│  └─────────────┘     │  init.sh     (env setup)     │  │
│                      └──────────────┬───────────────┘  │
│                                     │ read              │
│  ┌──────────────────────────────────▼───────────────┐  │
│  │                  agent.py (per run)               │  │
│  │                                                   │  │
│  │  [1] Load state ──────────────────────────────    │  │
│  │  [2] Summarise context                            │  │
│  │  [3] pick_next_task() ← harness decides           │  │
│  │  [4] call_gemini() ──────────────────────────┐   │  │
│  │                                              │   │  │
│  │  ┌───────────────────────────────────────┐   │   │  │
│  │  │           GEMINI API                  │◀──┘   │  │
│  │  │  (stateless reasoning engine)         │       │  │
│  │  └───────────────────────┬───────────────┘       │  │
│  │                          │ llm_output             │  │
│  │  [5] validate_task() ◀───┘                        │  │
│  │       ├── PASS → task.done=True, task.tested=True │  │
│  │       └── FAIL → log failure, exit(1), retry?     │  │
│  │  [6] save_tasks() + append_progress()             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Mapping to Real-World AI Agents

| This Project | Real-World Equivalent |
|---|---|
| `tasks.json` | GitHub Issues / Jira tickets / test specs |
| `progress.txt` | CI/CD run logs / audit trail |
| `state.json` | Agent memory store (Redis, DynamoDB) |
| `validate_task()` | Automated test suite (pytest, integration tests) |
| `pick_next_task()` | Task scheduler / dependency resolver |
| `init.sh` | Docker entrypoint / Terraform apply |
| One run = one task | One CI job = one atomic change |
| `os.replace()` atomic write | Database transaction / S3 conditional put |

Real systems like Devin, SWE-agent, and AutoGPT all implement variants of this pattern. The harness is what separates a demo from a production agent.

---

## 7. How to Run

### Setup
```bash
pip install google-generativeai
export GEMINI_API_KEY="your-key-here"
```

### Step 1 — Initialise (run once)
```bash
# Static tasks:
python initializer.py

# Or generate tasks from your own goal:
python initializer.py --goal "Build a REST API with JWT auth and PostgreSQL"
```

### Step 2 — Run the agent (repeat until all tasks done)
```bash
python agent.py
python agent.py
python agent.py
# ... one task completes per run
```

### Options
```bash
python agent.py --dry-run          # inspect state without calling API
python agent.py --retries 3        # retry validation up to 3 times
python initializer.py --force      # reset and re-initialise
```

### Expected output per run
```
── [1/6] Loading system state ──────────────────────────────────────
── [2/6] Context summary ───────────────────────────────────────────
Tasks: 1/7 done, 1/7 validated
Last progress entries:
[2025-01-15T09:01:45Z] DONE: Set up project structure...
── [3/6] Selecting task ────────────────────────────────────────────
  → [2] Implement database connection module with retry logic
── [4/6] Calling Gemini ────────────────────────────────────────────
── Agent reasoning & output ────────────────────────────────────────
  ... (Gemini output) ...
── [5/6] Validating ────────────────────────────────────────────────
  Attempt 1: Validation passed.
── [6/6] Updating state ────────────────────────────────────────────
✅ Task marked done + tested: Implement database connection module with retry logic
```

---

## Project Structure

```
long-running-agent-harness/
├── initializer.py   # Bootstrap: creates task contract + environment
├── agent.py         # Agent loop: one task per run, fully harness-controlled
├── utils.py         # All persistence: atomic reads/writes, task selection
├── tasks.json       # Task contract (source of truth)
├── progress.txt     # Append-only audit log
├── state.json       # Session metadata
├── init.sh          # Environment setup script
└── README.md
```

---

## Key Design Decisions

- **No frameworks**: Pure Python stdlib + `google-generativeai`. No LangChain, no AutoGen. The harness logic is explicit and auditable.
- **Atomic writes everywhere**: `os.replace()` ensures no file is ever half-written.
- **Validation is mandatory**: `tested: true` can only be set by `validate_task()` — there is no code path that bypasses it.
- **One task per run is a feature**: It makes the system observable, debuggable, and safe to run in CI/CD pipelines.
