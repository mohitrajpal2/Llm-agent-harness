# Llm-agent-harness

cd long-running-agent-harness
pip install google-generativeai
export GEMINI_API_KEY="your-key"

python initializer.py                                    # or --goal "your goal"
python agent.py                                          # repeat until done
python agent.py --dry-run                                # inspect state only




