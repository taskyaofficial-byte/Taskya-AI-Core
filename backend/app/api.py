import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from .config import DB_PATH
from .memory.store import MemoryStore
from .providers.groq_agent import TaskyaAgent

router = APIRouter()
memory = MemoryStore(DB_PATH)
agent = TaskyaAgent(memory)

class Task(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    language: str = Field(default="auto", max_length=30)

@router.post("/task")
async def task(x: Task):
    async def generate():
        response = await asyncio.to_thread(agent.run, x.message, x.language)
        yield response

    return StreamingResponse(generate(), media_type="text/event-stream")
