Build a production-quality minimal Python project demonstrating “Harness Engineering for Long-Running AI Agents” inspired by Anthropic’s research.

This project must not just implement basic task + progress tracking, but also cover advanced concepts like clean state management, validation, environment setup, and behavior shaping.

----------------------------
CORE REQUIREMENTS
----------------------------

1. Simulate a long-running agent across multiple sessions (multiple script runs).

2. Implement TWO main components:

A) Initializer (initializer.py)
- Runs only once
- Creates:
  - tasks.json → list of features/tasks with fields:
        { "task": "...", "done": false, "tested": false }
  - progress.txt → logs work
  - state.json → optional system metadata
  - init.sh → script to simulate environment setup (e.g., starting server)
- Generates tasks either:
  - static sample OR
  - from a user goal (bonus)

- Ensure tasks are structured and NOT easily modifiable (simulate test specs mindset)

---

B) Agent Loop (agent.py)

Each run must:

1. Load current system state:
   - tasks.json
   - progress.txt

2. “Get context” phase (IMPORTANT):
   - Read progress.txt
   - Read tasks.json
   - Print summary of system state

3. Pick exactly ONE incomplete task

4. Call GEMINI API with prompt including:
   - current progress
   - selected task
   - strict rules:
        - do only one task
        - leave system in clean state
        - explain clearly what was done

5. Simulate performing work (just text output is fine)

6. Clean State Enforcement (CRITICAL):
   - After execution:
        - no partial/incomplete work allowed
        - mark task done ONLY if fully complete
        - ensure no corruption of files
   - If failure → log it, don’t mark complete

7. Validation / Testing Layer (IMPORTANT GAP):
   - Add a function:
        validate_task(task)
   - Mark task:
        "tested": true only after validation
   - Simulate testing (basic checks are fine)
   - Prevent marking tasks complete without validation

8. Update system state:
   - Mark task completed
   - Append progress with timestamp + summary
   - Save all files cleanly

9. Enforce incremental execution:
   - Only 1 task per run

---

----------------------------
BEHAVIOR SHAPING (VERY IMPORTANT)
----------------------------

The system must FORCE the agent to behave properly:

- Always read progress before acting
- Always pick ONE task
- Always log actions
- Always validate before marking complete
- Never assume previous memory

Implement this explicitly in code comments and logic.

---

----------------------------
PROJECT STRUCTURE
----------------------------

long-running-agent-harness/
│
├── initializer.py
├── agent.py
├── utils.py
├── tasks.json
├── progress.txt
├── state.json
├── init.sh
└── README.md

---

----------------------------
README REQUIREMENTS (VERY IMPORTANT)
----------------------------

The README must clearly explain:

1. What is the long-running agent problem
   - LLM statelessness
   - context window limitation

2. What is harness engineering
   - system around LLM to manage memory + workflow

3. Core idea of this project
   - task tracking
   - progress logging
   - incremental execution

4. ADVANCED CONCEPTS (MUST INCLUDE):

   a) Clean State Requirement
      - why partial work causes failure
      - how this project enforces clean state

   b) Validation Layer
      - why agents falsely mark tasks complete
      - how testing fixes it

   c) Environment Initialization
      - role of initializer
      - why setup matters

   d) Behavior Shaping
      - how we force the agent to act like a disciplined engineer
      - importance of structured workflow

5. Architecture Diagram (text-based is fine)

6. How this project maps to real-world AI agents

7. How to run:
   - python initializer.py
   - python agent.py (multiple times)

---

----------------------------
BONUS FEATURES (HIGH VALUE)
----------------------------

- Auto-generate tasks from a user goal using LLM
- CLI interface using argparse
- Retry mechanism if validation fails
- Print “agent reasoning” steps
- Add priority field to tasks

---

----------------------------
OUTPUT FORMAT
----------------------------

Generate:
- Complete Python code (all files)
- Working logic
- Example tasks.json
- Example progress.txt
- Full README.md with explanations

Use simple Python (no heavy frameworks)
Add detailed comments explaining design decisions

Focus on clarity, correctness, and demonstrating real understanding of harness engineering.





