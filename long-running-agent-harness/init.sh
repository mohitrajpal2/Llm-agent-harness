#!/usr/bin/env bash
# init.sh — Simulates environment setup (run before agent.py in CI/CD).
# In production this would: start Docker, seed DB, export secrets, etc.

set -e

echo "[init] Creating virtual environment..."
python -m venv .venv

echo "[init] Installing dependencies..."
.venv/bin/pip install -q google-generativeai python-dotenv

echo "[init] Environment ready."
