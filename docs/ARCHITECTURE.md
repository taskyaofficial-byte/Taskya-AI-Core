# Taskya AI V1.5
User → FastAPI task API → background worker → Groq tool loop → search/browser/Docker/file tools → observe → re-plan → verify.
Browser uses Playwright. Code uses Docker with network disabled and resource limits. Files support PDF/Excel/CSV/text extraction. Frontend has live SSE events, browser STT/TTS and upload. Consequential intent has a human approval gate.
Production still needs durable queue/Postgres/object storage/HTTPS/tenant isolation/secret manager/real payment webhooks/stronger browser isolation.
