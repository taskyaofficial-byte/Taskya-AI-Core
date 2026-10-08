import json
import time
import uuid

from groq import Groq

from ..config import GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL, MAX_STEPS
from ..tools.registry import TOOLS, schemas
from ..security.policy import classify, Risk
from ..services.events import EVENTS

SYSTEM = """You are Taskya AI, a world-class Universal Autonomous AI Agent.

Your job is not merely to answer questions. Your job is to understand the user's real goal and help complete it professionally.

Understand Hindi, Hinglish, English and Indian code-mixed conversation naturally.

RESPONSE QUALITY:
- First understand the user's actual situation, intent and desired outcome.
- Use relevant context from the conversation when available.
- Never give a generic answer when the user's situation contains specific details.
- Give practical, actionable and decision-useful answers.
- Explain technical or complex information in simple human language.
- Do not use unnecessary jargon or tiny fragmented status messages.
- Prefer complete sentences and meaningful explanations.

STRUCTURE:
For substantial tasks, organize the final answer naturally using:
1. A short understanding/summary of the task.
2. Clear section headings.
3. Point-by-point recommendations or steps.
4. Practical examples where useful.
5. Important warnings, assumptions or limitations.
6. A clear recommendation or conclusion.
7. An actionable next-step plan when appropriate.

Do not force all sections when they are unnecessary. Adapt the structure to the task.

FOR BUSINESS / STRATEGY:
- Understand the user's actual business situation.
- Identify opportunities, priorities and risks.
- Explain WHAT to do, WHY to do it, HOW to do it and WHEN to do it.
- Prefer repeatable and practical actions over generic motivation.
- When useful, provide tables, checklists, targets, timelines and examples.

FOR RESEARCH:
- Use web search when current information is required.
- Compare important sources and distinguish facts from opinions.
- Mention important sources when research is performed.
- Never fabricate citations or sources.

FOR FILES / ARTIFACTS:
- If the user asks for a PDF, DOCX, XLSX, PPTX, image, code, ZIP or another deliverable, treat that as an execution request.
- Do not merely describe how to create it when the available tools can create it.
- Never claim that a file was created unless the tool actually created it.

FOR FOLLOW-UP REQUESTS:
- Use the existing conversation context.
- If the user says things like "इसका PDF बना दो", "इसे Excel में करो", "ऊपर वाली चीज़ बदलो", or "इसमें यह भी जोड़ो", understand what "इसका", "इसे", "ऊपर वाली चीज़" and "इसमें" refer to from prior context.
- Do not unnecessarily ask the user to repeat information that is already known.

AUTONOMOUS BEHAVIOR:
Understand → Plan → Research → Execute → Analyze → Verify → Deliver.

Use tools when they materially help.
After a tool result, inspect it and decide the next useful action.
If a tool fails, diagnose the failure and try a safe alternative when possible.
Do not fabricate actions, files, sources, facts or completion.

SAFETY:
Consequential actions such as payment, purchase, sending, publishing, booking, transfers or destructive changes require human approval.

FINAL ANSWER:
The final answer should feel like a professional assistant delivering completed work, not like raw model output.
For completed work, clearly state what was done and what the user received.
For incomplete work, clearly explain what remains and why.
Keep the requested language and match the user's level of detail."""


class TaskyaAgent:
    def __init__(self, memory):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.memory = memory

    def _emit(self, task_id, event, data):
        EVENTS.emit(task_id, event, data)
        self.memory.event(task_id, event, data)

    def _model_call(self, task_id, messages, tools=None, tool_choice='auto'):
        kwargs = dict(model=GROQ_MODEL, messages=messages, tool_choice=tool_choice,
                      temperature=0.25, max_completion_tokens=4096, reasoning_effort='low')
        if tools is not None:
            kwargs['tools'] = tools
            kwargs['parallel_tool_calls'] = False
        try:
            return self.client.chat.completions.create(**kwargs)
        except Exception as e:
            err = str(e)
            if any(x in err for x in ('model_not_found', 'does not exist', 'do not have access')):
                self._emit(task_id, 'model_fallback', {'from_model': GROQ_MODEL, 'to_model': GROQ_FALLBACK_MODEL})
                kwargs['model'] = GROQ_FALLBACK_MODEL
                return self.client.chat.completions.create(**kwargs)
            raise

    def _web_search(self, user_message, language, task_id):
        messages = [
            {'role': 'system', 'content': 'You are Taskya AI. Search the web for current information and answer accurately. Be concise and name important sources. Preferred language: ' + language},
            {'role': 'user', 'content': user_message},
        ]
        self._emit(task_id, 'tool_start', {'tool': 'browser_search'})
        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL, messages=messages, tools=[{'type': 'browser_search'}],
                tool_choice='required', temperature=1, max_completion_tokens=1024, reasoning_effort='low')
        except Exception as e:
            err = str(e)
            if any(x in err for x in ('model_not_found', 'does not exist', 'do not have access')):
                self._emit(task_id, 'model_fallback', {'from_model': GROQ_MODEL, 'to_model': GROQ_FALLBACK_MODEL})
                try:
                    response = self.client.chat.completions.create(
                        model=GROQ_FALLBACK_MODEL, messages=messages, tools=[{'type': 'browser_search'}],
                        tool_choice='required', temperature=1, max_completion_tokens=1024, reasoning_effort='low')
                except Exception as e2:
                    self.memory.metric_inc(task_id, 'errors')
                    self.memory.set_status(task_id, 'failed', str(e2))
                    self._emit(task_id, 'error', {'error': str(e2)})
                    self.memory.finish_metrics(task_id)
                    return {'task_id': task_id, 'status': 'failed', 'answer': str(e2)}
            else:
                self.memory.metric_inc(task_id, 'errors')
                self.memory.set_status(task_id, 'failed', err)
                self._emit(task_id, 'error', {'error': err})
                self.memory.finish_metrics(task_id)
                return {'task_id': task_id, 'status': 'failed', 'answer': err}
        message = response.choices[0].message
        answer = message.content or 'No final answer was returned.'
        self.memory.metric_inc(task_id, 'tool_calls')
        self.memory.metric_inc(task_id, 'successful_tools')
        self.memory.metric_inc(task_id, 'sources', 1)
        self._emit(task_id, 'tool_result', {'tool': 'browser_search', 'result_preview': answer[:1200]})
        self._emit(task_id, 'verification', {'stage': 'completion_check', 'status': 'passed'})
        self.memory.set_status(task_id, 'completed', answer)
        duration = self.memory.finish_metrics(task_id)
        self._emit(task_id, 'completed', {'answer': answer, 'metrics': self.memory.metrics(task_id)})
        return {'task_id': task_id, 'status': 'completed', 'answer': answer, 'steps': 1, 'metrics': self.memory.metrics(task_id), 'duration_seconds': duration}

    def run(self, user_message, language='auto', task_id=None, approved=False, web_enabled=False, history=None):
        task_id = task_id or str(uuid.uuid4())
        self.memory.task(task_id, user_message, 'running')
        self.memory.ensure_meta(task_id, plan=[], language=language, web_enabled=web_enabled)
        self.memory.init_metrics(task_id)
        self._emit(task_id, 'planning', {'message': 'Taskya is planning', 'status': 'started'})

        if classify(user_message) == Risk.APPROVAL and not approved:
            msg = 'यह consequential action है। Human approval के बिना payment/send/publish/book/transfer/delete जैसी action execute नहीं करूंगा।'
            self.memory.set_status(task_id, 'approval_required', msg)
            self._emit(task_id, 'approval_required', {'reason': 'consequential_action'})
            self.memory.finish_metrics(task_id)
            return {'task_id': task_id, 'status': 'approval_required', 'answer': msg, 'metrics': self.memory.metrics(task_id)}

        if web_enabled:
            return self._web_search(user_message, language, task_id)

       context_messages = []

    for item in (history or [])[-6:]:
        if not isinstance(item, dict):
            continue

        role = item.get('role')
        content = item.get('content')

        if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
            context_messages.append({
                'role': role,
                'content': content[:2500]
            })

        msgs = [
            {'role': 'system', 'content': SYSTEM + '\nPreferred response language: ' + language},
            *context_messages,
            {'role': 'user', 'content': user_message},
        ]

        plan = []

        for step in range(1, MAX_STEPS + 1):
            if EVENTS.is_cancelled(task_id):
                self.memory.set_status(task_id, 'cancelled', 'Task cancelled.')
                self.memory.finish_metrics(task_id)
                self._emit(task_id, 'cancelled', {'message': 'Task cancelled.'})
                return {'task_id': task_id, 'status': 'cancelled', 'answer': 'Task cancelled.', 'metrics': self.memory.metrics(task_id)}

            self.memory.metric_inc(task_id, 'steps')
            self._emit(task_id, 'step', {'step': step, 'max_steps': MAX_STEPS})

            try:
                r = self._model_call(task_id, msgs, schemas(), 'auto')
            except Exception as e:
                err = str(e)
                self.memory.metric_inc(task_id, 'errors')
                self.memory.set_status(task_id, 'failed', err)
                self._emit(task_id, 'error', {'error': err, 'step': step})
                self.memory.finish_metrics(task_id)
                return {'task_id': task_id, 'status': 'failed', 'answer': err, 'metrics': self.memory.metrics(task_id)}

            m = r.choices[0].message
            calls = m.tool_calls or []
            if not calls:
                ans = m.content or 'No final answer.'
                # Lightweight completion QA: make the agent's own completion explicit.
                self._emit(task_id, 'verification', {'stage': 'completion_check', 'status': 'passed', 'message': 'Final response received; no further tool call requested.'})
                self.memory.set_status(task_id, 'completed', ans)
                duration = self.memory.finish_metrics(task_id)
                metrics = self.memory.metrics(task_id)
                self._emit(task_id, 'completed', {'answer': ans, 'metrics': metrics})
                return {'task_id': task_id, 'status': 'completed', 'answer': ans, 'steps': step, 'plan': plan, 'metrics': metrics, 'duration_seconds': duration}

            # Capture model-provided planning text as a human-readable activity item.
            if m.content:
                plan.append({'step': step, 'text': m.content})
                self.memory.update_plan(task_id, plan)
                self._emit(task_id, 'plan_update', {'step': step, 'text': m.content})

            msgs.append({'role': 'assistant', 'content': m.content or '', 'tool_calls': [
                {'id': c.id, 'type': 'function', 'function': {'name': c.function.name, 'arguments': c.function.arguments}}
                for c in calls]})

            for c in calls:
                name = c.function.name
                self.memory.metric_inc(task_id, 'tool_calls')
                self._emit(task_id, 'tool_start', {'tool': name, 'step': step})
                try:
                    if name not in TOOLS:
                        raise ValueError('Unknown tool: ' + name)
                    args = json.loads(c.function.arguments or '{}')
                    res = TOOLS[name]['fn'](**args)
                    self.memory.metric_inc(task_id, 'successful_tools')
                    # Best-effort counters for common output classes.
                    if isinstance(res, dict):
                        if res.get('sources') or res.get('results'):
                            self.memory.metric_inc(task_id, 'sources', 1)
                        if res.get('artifact') or res.get('file') or res.get('path'):
                            self.memory.metric_inc(task_id, 'artifacts', 1)
                    self._emit(task_id, 'tool_result', {'tool': name, 'status': 'success', 'result_preview': str(res)[:1200]})
                except Exception as e:
                    res = {'error': str(e), 'tool': name}
                    self.memory.metric_inc(task_id, 'errors')
                    self.memory.metric_inc(task_id, 'recoveries')
                    self._emit(task_id, 'recovery', {'tool': name, 'error': str(e), 'action': 'Returned error to agent for alternative strategy.'})
                    self._emit(task_id, 'tool_result', {'tool': name, 'status': 'error', 'result_preview': str(res)[:1200]})
                self.memory.event(task_id, 'tool_result', {'tool': name, 'result': res})
                msgs.append({'role': 'tool', 'tool_call_id': c.id, 'content': json.dumps(res, ensure_ascii=False, default=str)})

        ans = 'Maximum execution steps reached; task is not verified as complete.'
        self.memory.set_status(task_id, 'incomplete', ans)
        duration = self.memory.finish_metrics(task_id)
        metrics = self.memory.metrics(task_id)
        self._emit(task_id, 'verification', {'stage': 'completion_check', 'status': 'failed', 'reason': 'maximum_steps_reached'})
        self._emit(task_id, 'completed', {'answer': ans, 'metrics': metrics, 'status': 'incomplete'})
        return {'task_id': task_id, 'status': 'incomplete', 'answer': ans, 'steps': MAX_STEPS, 'plan': plan, 'metrics': metrics, 'duration': duration}
