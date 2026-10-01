import json,uuid
from groq import Groq
from ..config import GROQ_API_KEY,GROQ_MODEL,GROQ_FALLBACK_MODEL,MAX_STEPS
from ..tools.registry import TOOLS,schemas
from ..security.policy import classify,Risk
from ..services.events import EVENTS
SYSTEM="""You are Taskya AI, an India-first autonomous AI agent. Understand Hindi, Hinglish, English and Indian code-mixed conversation. Accomplish the user's real goal. Use a ReAct loop: plan, call a tool, inspect its result, re-plan and verify. Use web search for current facts, browser for websites, Docker Python for computation/data work, and file intelligence for uploaded documents. Never claim success without evidence. If a tool fails, diagnose and try a safe alternative. Consequential actions such as payment, purchase, sending, publishing, booking, transfers or destructive changes require human approval. Keep answers in the requested language."""
class TaskyaAgent:
 def __init__(self,memory):self.client=Groq(api_key=GROQ_API_KEY);self.memory=memory
 def run(self,user_message,language='auto',task_id=None,approved=False,web_enabled=False):
  task_id=task_id or str(uuid.uuid4());self.memory.task(task_id,user_message,'running');EVENTS.emit(task_id,'planning',{'message':'Taskya is planning'})
  if classify(user_message)==Risk.APPROVAL and not approved:
   msg='यह consequential action है। Human approval के बिना payment/send/publish/book/transfer/delete जैसी action execute नहीं करूंगा।';self.memory.set_status(task_id,'approval_required',msg);EVENTS.emit(task_id,'approval_required',{'reason':'consequential_action'});return {'task_id':task_id,'status':'approval_required','answer':msg}
  web_note='\nUser explicitly enabled web search; use the web search tool when current/public web information is needed.' if web_enabled else ''
  msgs=[{'role':'system','content':SYSTEM+web_note+'\nPreferred response language: '+language},{'role':'user','content':user_message}]
  for step in range(1,MAX_STEPS+1):
   if EVENTS.is_cancelled(task_id):self.memory.set_status(task_id,'cancelled','Task cancelled.');return {'task_id':task_id,'status':'cancelled','answer':'Task cancelled.'}
   EVENTS.emit(task_id,'step',{'step':step});self.memory.event(task_id,'agent_step',{'step':step})
   try:
    r=self.client.chat.completions.create(model=GROQ_MODEL,messages=msgs,tools=schemas(),tool_choice='auto',parallel_tool_calls=False,temperature=0.2)
   except Exception as e:
    # Production safety net: if Render still has an old/stale model setting,
    # retry once on a current Groq production model instead of exposing a
    # model_not_found 404 to the user.
    err=str(e)
    if 'model_not_found' in err or 'does not exist' in err or 'do not have access' in err:
     try:
      EVENTS.emit(task_id,'model_fallback',{'from_model':GROQ_MODEL,'to_model':GROQ_FALLBACK_MODEL})
      r=self.client.chat.completions.create(model=GROQ_FALLBACK_MODEL,messages=msgs,tools=schemas(),tool_choice='auto',parallel_tool_calls=False,temperature=0.2)
     except Exception as e2:
      self.memory.set_status(task_id,'failed',str(e2));EVENTS.emit(task_id,'error',{'error':str(e2)});return {'task_id':task_id,'status':'failed','answer':str(e2)}
    else:
     self.memory.set_status(task_id,'failed',err);EVENTS.emit(task_id,'error',{'error':err});return {'task_id':task_id,'status':'failed','answer':err}
   m=r.choices[0].message;calls=m.tool_calls or []
   if not calls:
    ans=m.content or 'No final answer.';self.memory.set_status(task_id,'completed',ans);EVENTS.emit(task_id,'completed',{'answer':ans});return {'task_id':task_id,'status':'completed','answer':ans,'steps':step}
   msgs.append({'role':'assistant','content':m.content or '','tool_calls':[{'id':c.id,'type':'function','function':{'name':c.function.name,'arguments':c.function.arguments}} for c in calls]})
   for c in calls:
    EVENTS.emit(task_id,'tool_start',{'tool':c.function.name})
    try:args=json.loads(c.function.arguments or '{}');res=TOOLS[c.function.name]['fn'](**args)
    except Exception as e:res={'error':str(e),'tool':getattr(c.function,'name','unknown')}
    EVENTS.emit(task_id,'tool_result',{'tool':c.function.name,'result_preview':str(res)[:1200]});self.memory.event(task_id,'tool_result',{'tool':c.function.name,'result':res});msgs.append({'role':'tool','tool_call_id':c.id,'content':json.dumps(res,ensure_ascii=False,default=str)})
  ans='Maximum execution steps reached; task is not verified as complete.';self.memory.set_status(task_id,'incomplete',ans);return {'task_id':task_id,'status':'incomplete','answer':ans,'steps':MAX_STEPS}
