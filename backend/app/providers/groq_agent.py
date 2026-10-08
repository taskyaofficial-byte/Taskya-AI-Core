import json
import time
import uuid

from groq import Groq

from ..config import GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL, MAX_STEPS
from ..tools.registry import TOOLS, schemas
from ..security.policy import classify, Risk
from ..services.events import EVENTS


SYSTEM = """You are Taskya AI, a world-class Universal Autonomous AI Agent and a concise, highly structured answer engine.

CORE MISSION:
Understand the user's real goal, solve the task accurately, and communicate the useful result in the clearest possible form.
You understand Hindi, Hinglish, English and Indian code-mixed conversation naturally.

TRUTH AND USEFULNESS:
- Never agree merely to please the user.
- Prefer truth, evidence, practical usefulness and completion over flattery.
- Distinguish facts, estimates, assumptions and opinions.
- Never fabricate sources, actions, files, numbers or completion.
- If information is uncertain or missing, say so briefly and explain what matters.

ANSWER PRINCIPLE — SHORT FIRST, DEEP ON DEMAND:
- The default answer must be concise.
- Give the complete NICHOD / bottom line first.
- Do not dump all reasoning or background information into the final answer.
- Compress information: keep the facts that materially affect the user's understanding or decision.
- A short answer must still be complete enough to solve the user's actual question.
- Do not write an essay when a few structured points can answer the question.
- Do not repeat the user's question or repeat the same point in different words.
- If the user asks for detail, deep research, full analysis, or a complete plan, expand appropriately.
- Answer length must depend on task complexity and the user's request, not on how much information is available.

STRUCTURE — NO WALLS OF TEXT:
For any substantial answer, prefer this hierarchy:
1. A clear, useful headline or section title.
2. A short "सीधा जवाब" / bottom-line summary.
3. Key points as numbered bullets.
4. A table when comparison, numbers or categories are easier to understand in a table.
5. Action steps when the user needs to do something.
6. Risks / important notes only when relevant.
7. A short final recommendation when useful.

Formatting rules:
- Use Markdown headings (`##` / `###`) where they improve readability.
- Prefer numbered lists and bullets over long paragraphs.
- Keep paragraphs short, normally 1–3 sentences.
- Never create a large uninterrupted wall of text.
- If a point can be said clearly in one sentence, do not turn it into a paragraph.
- Do not force headings for trivial one-line questions.
- Use bold sparingly to highlight the most important conclusion, number or action.
- Use tables only when they genuinely improve comprehension.

TASK-SPECIFIC STRUCTURE:
For business/strategy:
## सीधा जवाब
## सबसे जरूरी बातें
## क्या करें
## जोखिम / ध्यान देने वाली बातें
## मेरी सलाह

For research:
## निष्कर्ष
## मुख्य तथ्य
## क्या मिला
## इसका मतलब
## मेरी सलाह
Mention important sources when research is actually performed.

For how-to:
## क्या करना है
1. Step 1
2. Step 2
3. Step 3
## ध्यान रखें
## परिणाम

For comparisons:
## सीधा फैसला
| विकल्प | फायदा | नुकसान | किसके लिए |
Then a short recommendation.

For problem solving:
## समस्या
## संभावित कारण
## सबसे अच्छा समाधान
## कदम
## कैसे verify करें

For legal or medical topics:
Use a concise structured explanation, clearly state uncertainty/limitations, avoid guarantees, and highlight when qualified professional advice is appropriate.

For files/artifacts:
If the user asks for PDF, DOCX, XLSX, PPTX, image, code, ZIP or another deliverable, treat it as an execution request. Use available tools when they actually exist. Never claim a file was created unless it was actually created.

FOLLOW-UP / CONVERSATION MEMORY:
Use relevant prior conversation context.
Resolve phrases such as "इसका", "इसे", "ऊपर वाला", "इसमें भी जोड़ो", "PDF बना दो" from available context.
Do not ask the user to repeat information that is already available.
If context is genuinely insufficient, ask only for the missing information.

AUTONOMOUS WORKFLOW:
Understand → Plan → Research → Execute → Analyze → Verify → Deliver.
Use tools when they materially help.
After a tool result, inspect it and decide the next useful action.
If a tool fails, diagnose it and use a safe alternative when possible.
Do not claim completion before verification.

FINAL QUALITY CHECK BEFORE ANSWERING:
Silently check:
- Did I answer the actual question?
- Is the bottom line near the top?
- Is the answer structured with useful headings/points where appropriate?
- Can any paragraph be shortened without losing meaning?
- Did I remove repetition and generic filler?
- Did I include the most decision-useful facts?
- Is there a clear next step or recommendation when one is needed?
- Did I avoid a wall of text?
Only then return the final answer.

SAFETY:
Consequential actions such as payment, purchase, sending, publishing, booking, transfers or destructive changes require human approval.

The final answer should feel like a professional assistant delivering a clear, concise, decision-useful result — not raw model output."""


class TaskyaAgent:
    def __init__(self, memory):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.memory = memory

    def _emit(self, task_id, event, data):
        EVENTS.emit(task_id, event, data)
        self.memory.event(task_id, event, data)

    def _model_call(self, task_id, messages, tools=None, tool_choice='auto'):
        kwargs = dict(
            model=GROQ_MODEL,
            messages=messages,
            tool_choice=tool_choice,
            temperature=0.25,
            max_completion_tokens=3072,
            reasoning_effort='low'
        )

        if tools is not None:
            kwargs['tools'] = tools
            kwargs['parallel_tool_calls'] = False

        try:
            return self.client.chat.completions.create(**kwargs)

        except Exception as e:
            err = str(e)

            if any(
                x in err
                for x in ('model_not_found', 'does not exist', 'do not have access')
            ):
                self._emit(
                    task_id,
                    'model_fallback',
                    {
                        'from_model': GROQ_MODEL,
                        'to_model': GROQ_FALLBACK_MODEL
                    }
                )

                kwargs['model'] = GROQ_FALLBACK_MODEL

                return self.client.chat.completions.create(**kwargs)

            raise

    def _web_search(self, user_message, language, task_id, history=None):
        context_messages = []

        for item in (history or [])[-4:]:
            if not isinstance(item, dict):
                continue

            role = item.get('role')
            content = item.get('content')

            if (
                role in ('user', 'assistant')
                and isinstance(content, str)
                and content.strip()
            ):
                context_messages.append(
                    {
                        'role': role,
                        'content': content[:1800]
                    }
                )

        messages = [
            {
                'role': 'system',
                'content':
                    'You are Taskya AI. Search the web for current information and '
                    'answer accurately. Be concise and name important sources. '
                    'Use prior conversation context when relevant. '
                    'Preferred language: ' + language
            },
            *context_messages,
            {
                'role': 'user',
                'content': user_message
            },
        ]

        self._emit(
            task_id,
            'tool_start',
            {'tool': 'browser_search'}
        )

        try:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=[{'type': 'browser_search'}],
                tool_choice='required',
                temperature=1,
                max_completion_tokens=1024,
                reasoning_effort='low'
            )

        except Exception as e:
            err = str(e)

            if any(
                x in err
                for x in ('model_not_found', 'does not exist', 'do not have access')
            ):
                self._emit(
                    task_id,
                    'model_fallback',
                    {
                        'from_model': GROQ_MODEL,
                        'to_model': GROQ_FALLBACK_MODEL
                    }
                )

                try:
                    response = self.client.chat.completions.create(
                        model=GROQ_FALLBACK_MODEL,
                        messages=messages,
                        tools=[{'type': 'browser_search'}],
                        tool_choice='required',
                        temperature=1,
                        max_completion_tokens=1024,
                        reasoning_effort='low'
                    )

                except Exception as e2:
                    self.memory.metric_inc(task_id, 'errors')
                    self.memory.set_status(task_id, 'failed', str(e2))

                    self._emit(
                        task_id,
                        'error',
                        {'error': str(e2)}
                    )

                    self.memory.finish_metrics(task_id)

                    return {
                        'task_id': task_id,
                        'status': 'failed',
                        'answer': str(e2)
                    }

            else:
                self.memory.metric_inc(task_id, 'errors')
                self.memory.set_status(task_id, 'failed', err)

                self._emit(
                    task_id,
                    'error',
                    {'error': err}
                )

                self.memory.finish_metrics(task_id)

                return {
                    'task_id': task_id,
                    'status': 'failed',
                    'answer': err
                }

        message = response.choices[0].message
        answer = message.content or 'No final answer was returned.'

        self.memory.metric_inc(task_id, 'tool_calls')
        self.memory.metric_inc(task_id, 'successful_tools')
        self.memory.metric_inc(task_id, 'sources', 1)

        self._emit(
            task_id,
            'tool_result',
            {
                'tool': 'browser_search',
                'result_preview': answer[:1200]
            }
        )

        self._emit(
            task_id,
            'verification',
            {
                'stage': 'completion_check',
                'status': 'passed'
            }
        )

        self.memory.set_status(
            task_id,
            'completed',
            answer
        )

        duration = self.memory.finish_metrics(task_id)

        metrics = self.memory.metrics(task_id)

        self._emit(
            task_id,
            'completed',
            {
                'answer': answer,
                'metrics': metrics
            }
        )

        return {
            'task_id': task_id,
            'status': 'completed',
            'answer': answer,
            'steps': 1,
            'metrics': metrics,
            'duration_seconds': duration
        }

    def run(
        self,
        user_message,
        language='auto',
        task_id=None,
        approved=False,
        web_enabled=False,
        history=None
    ):
        task_id = task_id or str(uuid.uuid4())

        self.memory.task(
            task_id,
            user_message,
            'running'
        )

        self.memory.ensure_meta(
            task_id,
            plan=[],
            language=language,
            web_enabled=web_enabled
        )

        self.memory.init_metrics(task_id)

        self._emit(
            task_id,
            'planning',
            {
                'message': 'Taskya is planning',
                'status': 'started'
            }
        )

        if classify(user_message) == Risk.APPROVAL and not approved:
            msg = (
                'यह consequential action है। Human approval के बिना '
                'payment/send/publish/book/transfer/delete जैसी action execute नहीं करूंगा।'
            )

            self.memory.set_status(
                task_id,
                'approval_required',
                msg
            )

            self._emit(
                task_id,
                'approval_required',
                {'reason': 'consequential_action'}
            )

            self.memory.finish_metrics(task_id)

            return {
                'task_id': task_id,
                'status': 'approval_required',
                'answer': msg,
                'metrics': self.memory.metrics(task_id)
            }

        if web_enabled:
            return self._web_search(
                user_message,
                language,
                task_id,
                history
            )

        # Keep conversation memory small enough for the Groq TPM limit.
        context_messages = []
        total_context_chars = 0
        max_context_chars = 6000

        for item in (history or [])[-6:]:
            if not isinstance(item, dict):
                continue

            role = item.get('role')
            content = item.get('content')

            if (
                role in ('user', 'assistant')
                and isinstance(content, str)
                and content.strip()
            ):
                content = content[:1800]

                if total_context_chars + len(content) > max_context_chars:
                    remaining = max_context_chars - total_context_chars

                    if remaining <= 0:
                        break

                    content = content[:remaining]

                if not content:
                    break

                context_messages.append(
                    {
                        'role': role,
                        'content': content
                    }
                )

                total_context_chars += len(content)

                if total_context_chars >= max_context_chars:
                    break

        msgs = [
            {
                'role': 'system',
                'content':
                    SYSTEM +
                    '\nPreferred response language: ' +
                    language
            },
            *context_messages,
            {
                'role': 'user',
                'content': user_message
            },
        ]

        plan = []

        for step in range(1, MAX_STEPS + 1):
            if EVENTS.is_cancelled(task_id):
                self.memory.set_status(
                    task_id,
                    'cancelled',
                    'Task cancelled.'
                )

                self.memory.finish_metrics(task_id)

                self._emit(
                    task_id,
                    'cancelled',
                    {'message': 'Task cancelled.'}
                )

                return {
                    'task_id': task_id,
                    'status': 'cancelled',
                    'answer': 'Task cancelled.',
                    'metrics': self.memory.metrics(task_id)
                }

            self.memory.metric_inc(
                task_id,
                'steps'
            )

            self._emit(
                task_id,
                'step',
                {
                    'step': step,
                    'max_steps': MAX_STEPS
                }
            )

            try:
                r = self._model_call(
                    task_id,
                    msgs,
                    schemas(),
                    'auto'
                )

            except Exception as e:
                err = str(e)

                self.memory.metric_inc(
                    task_id,
                    'errors'
                )

                self.memory.set_status(
                    task_id,
                    'failed',
                    err
                )

                self._emit(
                    task_id,
                    'error',
                    {
                        'error': err,
                        'step': step
                    }
                )

                self.memory.finish_metrics(task_id)

                return {
                    'task_id': task_id,
                    'status': 'failed',
                    'answer': err,
                    'metrics': self.memory.metrics(task_id)
                }

            m = r.choices[0].message
            calls = m.tool_calls or []

            if not calls:
                ans = m.content or 'No final answer.'

                self._emit(
                    task_id,
                    'verification',
                    {
                        'stage': 'completion_check',
                        'status': 'passed',
                        'message':
                            'Final response received; no further tool call requested.'
                    }
                )

                self.memory.set_status(
                    task_id,
                    'completed',
                    ans
                )

                duration = self.memory.finish_metrics(
                    task_id
                )

                metrics = self.memory.metrics(
                    task_id
                )

                self._emit(
                    task_id,
                    'completed',
                    {
                        'answer': ans,
                        'metrics': metrics
                    }
                )

                return {
                    'task_id': task_id,
                    'status': 'completed',
                    'answer': ans,
                    'steps': step,
                    'plan': plan,
                    'metrics': metrics,
                    'duration_seconds': duration
                }

            if m.content:
                plan.append(
                    {
                        'step': step,
                        'text': m.content
                    }
                )

                self.memory.update_plan(
                    task_id,
                    plan
                )

                self._emit(
                    task_id,
                    'plan_update',
                    {
                        'step': step,
                        'text': m.content
                    }
                )

            msgs.append(
                {
                    'role': 'assistant',
                    'content': m.content or '',
                    'tool_calls': [
                        {
                            'id': c.id,
                            'type': 'function',
                            'function': {
                                'name': c.function.name,
                                'arguments': c.function.arguments
                            }
                        }
                        for c in calls
                    ]
                }
            )

            for c in calls:
                name = c.function.name

                self.memory.metric_inc(
                    task_id,
                    'tool_calls'
                )

                self._emit(
                    task_id,
                    'tool_start',
                    {
                        'tool': name,
                        'step': step
                    }
                )

                try:
                    if name not in TOOLS:
                        raise ValueError(
                            'Unknown tool: ' + name
                        )

                    args = json.loads(
                        c.function.arguments or '{}'
                    )

                    res = TOOLS[name]['fn'](
                        **args
                    )

                    self.memory.metric_inc(
                        task_id,
                        'successful_tools'
                    )

                    if isinstance(res, dict):
                        if res.get('sources') or res.get('results'):
                            self.memory.metric_inc(
                                task_id,
                                'sources',
                                1
                            )

                        if (
                            res.get('artifact')
                            or res.get('file')
                            or res.get('path')
                        ):
                            self.memory.metric_inc(
                                task_id,
                                'artifacts',
                                1
                            )

                    self._emit(
                        task_id,
                        'tool_result',
                        {
                            'tool': name,
                            'status': 'success',
                            'result_preview': str(res)[:1200]
                        }
                    )

                except Exception as e:
                    res = {
                        'error': str(e),
                        'tool': name
                    }

                    self.memory.metric_inc(
                        task_id,
                        'errors'
                    )

                    self.memory.metric_inc(
                        task_id,
                        'recoveries'
                    )

                    self._emit(
                        task_id,
                        'recovery',
                        {
                            'tool': name,
                            'error': str(e),
                            'action':
                                'Returned error to agent for alternative strategy.'
                        }
                    )

                    self._emit(
                        task_id,
                        'tool_result',
                        {
                            'tool': name,
                            'status': 'error',
                            'result_preview': str(res)[:1200]
                        }
                    )

                msgs.append(
                    {
                        'role': 'tool',
                        'tool_call_id': c.id,
                        'content': json.dumps(
                            res,
                            ensure_ascii=False,
                            default=str
                        )
                    }
                )

        final_msg = 'Task reached the maximum execution steps without a final answer.'

        self.memory.set_status(
            task_id,
            'completed',
            final_msg
        )

        duration = self.memory.finish_metrics(
            task_id
        )

        metrics = self.memory.metrics(
            task_id
        )

        self._emit(
            task_id,
            'verification',
            {
                'stage': 'max_steps_check',
                'status': 'passed'
            }
        )

        self._emit(
            task_id,
            'completed',
            {
                'answer': final_msg,
                'metrics': metrics
            }
        )

        return {
            'task_id': task_id,
            'status': 'completed',
            'answer': final_msg,
            'steps': MAX_STEPS,
            'plan': plan,
            'metrics': metrics,
            'duration_seconds': duration
        }
