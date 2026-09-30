# Frontend ↔ Render backend connection

The Vercel frontend must point to the Render API, not localhost.

`frontend/config.js` contains:

`window.TASKYA_API_BASE = 'https://taskya-ai-core.onrender.com/api';`

The backend exposes:

- `GET /` health
- `GET /api/health`
- `POST /api/chat` compatibility endpoint
- `POST /api/task` async agent endpoint
- `GET /api/task/{task_id}/events` SSE progress
- `POST /api/upload`

For Render, use:

`pip install -r backend/requirements.txt && playwright install chromium`

Start command:

`uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

If your Render service URL changes, update only `frontend/config.js` and redeploy the frontend.
