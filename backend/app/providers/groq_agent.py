import json, uuid
from groq import Groq
from ..config import GROQ_API_KEY, GROQ_MODEL, MAX_STEPS
from ..tools.registry import TOOLS, schemas
from ..security.policy import classify, Risk

SYSTEM = """You are Taskya AI, an India-first autonomous AI agent.
Understand Hindi, Hinglish, English and natural Indian code-mixed conversation.
Your job is to accomplish the user's real goal, not merely chat.
Use a ReAct-style dual loop: reason about the next useful action, call a tool, inspect its result, then re-plan until the task is complete or safely blocked.
Use live web search only when freshness or external facts are needed. Use calculator for arithmetic and workspace tools for files.
Never claim a tool action succeeded without evidence. If a tool fails, diagnose it and try a safe alternative when possible. Verify important outputs before finishing.
For consequential actions such as payments, purchases, sending messages, publishing, booking, transfers or destructive changes, require approval; current V1 has no executable tools for those actions.
Do not invent sources, files, numbers, or completed actions. Reply naturally in the user's language.
"""

class TaskyaAgent:
    def __init__(self, memory):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.memory = memory

    def run(self, user_message, language="auto", task_id=None):
        task_id = task_id or str(uuid.uuid4())
        self.memory.task(task_id, user_message)
        if classify(user_message) != Risk.LOW:
            msg = "यह consequential action है। अभी मैं इसे खुद execute नहीं करूंगा; सुरक्षित planning/research कर सकता हूँ।"
            self.memory.finish(task_id, "approval_required", msg)
            return {"task_id": task_id, "status": "approval_required", "answer": msg}

        lang_hint = "auto" if language == "auto" else language
        msgs = [
            {"role": "system", "content": SYSTEM + f"\nPreferred response language: {lang_hint}.",},
            {"role": "user", "content": user_message},
        ]
        for step in range(1, MAX_STEPS + 1):
            self.memory.event(task_id, "agent_step", {"step": step})
            r = self.client.chat.completions.create(
                model=GROQ_MODEL, messages=msgs, tools=schemas(),
                tool_choice="auto", parallel_tool_calls=True, temperature=0.2
            )
            m = r.choices[0].message
            calls = m.tool_calls or []
            if not calls:
                ans = m.content or "No final answer."
                self.memory.finish(task_id, "completed", ans)
                return {"task_id": task_id, "status": "completed", "answer": ans, "steps": step}

            msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls
            ]})
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                    res = TOOLS[c.function.name]["fn"](**args)
                except Exception as e:
                    res = {"error": str(e), "tool": getattr(c.function, "name", "unknown")}
                self.memory.event(task_id, "tool_result", {"tool": c.function.name, "result": res})
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(res, ensure_ascii=False, default=str)})

        ans = "Maximum execution steps reached; task is not verified as complete."
        self.memory.finish(task_id, "incomplete", ans)
        return {"task_id": task_id, "status": "incomplete", "answer": ans, "steps": MAX_STEPS}
