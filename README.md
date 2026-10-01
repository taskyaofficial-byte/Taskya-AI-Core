# Taskya AI V1.5
A substantially upgraded India-first autonomous AI agent core.

## Included
- Groq tool-calling ReAct loop + Tavily live search
- Playwright browser: DOM text + screenshot + inspect/click/fill
- Docker Python sandbox: no network + resource limits
- PDF/Excel/CSV/text intelligence
- Artifact/workspace tools
- Live SSE task progress + cancellation
- Human approval gate + resume
- Browser speech-to-text + speech synthesis
- Hindi/Hinglish/English/regional selector
- File upload

## Run on laptop
1. Install Python 3.11+ and Docker Desktop.
2. Copy `.env.example` to `.env`; add Groq/Tavily keys.
3. `python -m venv .venv` then activate it.
4. `pip install -r backend/requirements.txt`
5. `python -m playwright install chromium`
6. `uvicorn backend.app.main:app --reload --port 8000`
7. Open `frontend/index.html`.

## Important
This is not yet a finished cloud product or proven Manus replacement. Production auth/payment/multi-tenant infrastructure and stronger isolation still require deployment credentials and hardening. Do not claim superiority until benchmarked.


### Groq model note

Use `GROQ_MODEL=openai/gpt-oss-120b`. Groq retired `llama-3.3-70b-versatile` for developer/free usage; the agent also contains a runtime fallback to `openai/gpt-oss-20b` so a stale Render environment variable does not immediately break chat.
