# Taskya AI V1.5

Taskya V1.5 upgrades the original LLM+tools loop into a worker-oriented agent foundation.

## Workers
- Browser: Playwright DOM/text/link extraction and screenshots.
- Code sandbox: Docker execution with no network, CPU/memory/PID limits.
- Documents: PDF/text extraction and optional OCR.
- Computer: optional host control, disabled by default.
- Integrations: MCP HTTP adapter foundation.

## Orchestration
`Task -> Planner/LLM -> Worker -> Observation -> Re-plan -> Verify -> Result`

The included TaskManager supports queued/running/paused/resumed/cancelled state and event streams for a future SSE/WebSocket transport.

## Safety
Computer control is opt-in. Consequential actions must remain behind explicit human approval. Docker execution is isolated from the host network.
