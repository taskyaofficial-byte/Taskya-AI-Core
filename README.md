# Taskya AI — Core

India-first autonomous AI agent starter. This build is the renamed/refined successor to the earlier AagyaAI starter.

## Current core
- Groq tool-calling agent with ReAct-style Plan → Act → Observe → Verify loop
- Default model: `openai/gpt-oss-120b` (override with `GROQ_MODEL`)
- Tavily live web search tool
- Calculator + safe workspace file tools + artifact writer
- SQLite task/event memory
- Approval boundary for consequential actions
- Hindi/Hinglish/English-aware system prompt
- Frontend language selector + browser Speech-to-Text button

## Laptop setup
1. Install Python 3.11+ and VS Code.
2. Copy `.env.example` to `.env`.
3. Add `GROQ_API_KEY`; add `TAVILY_API_KEY` for live web search.
4. Create venv: `python -m venv .venv`
5. Activate it, then `pip install -r backend/requirements.txt`
6. Run from project root: `uvicorn backend.app.main:app --reload --port 8000`
7. Open `frontend/index.html` in a browser.

## Important
This is an engineering foundation, not a finished Manus replacement. Browser/computer control, isolated code execution, uploads/OCR, live SSE task events, auth/billing and production workers are the next major modules.

Do not claim Taskya AI is better/faster than Manus until a repeatable benchmark proves it.
