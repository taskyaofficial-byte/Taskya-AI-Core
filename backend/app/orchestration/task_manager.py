import asyncio, time, uuid
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TaskState:
    id: str
    message: str
    status: str = 'queued'
    created_at: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    pause: asyncio.Event = field(default_factory=asyncio.Event)
    cancel: bool = False

class TaskManager:
    def __init__(self):
        self.tasks: dict[str, TaskState] = {}
        self._lock = asyncio.Lock()

    async def create(self, message: str) -> TaskState:
        async with self._lock:
            t=TaskState(str(uuid.uuid4()), message)
            t.pause.set(); self.tasks[t.id]=t; return t

    async def emit(self, task_id, event, data=None):
        t=self.tasks[task_id]; t.events.append({'ts':time.time(),'event':event,'data':data or {}})

    async def wait_if_paused(self, t):
        await t.pause.wait()

    async def pause_task(self, task_id): self.tasks[task_id].pause.clear(); self.tasks[task_id].status='paused'
    async def resume_task(self, task_id): self.tasks[task_id].pause.set(); self.tasks[task_id].status='running'
    async def cancel_task(self, task_id): self.tasks[task_id].cancel=True; self.tasks[task_id].pause.set(); self.tasks[task_id].status='cancelled'
