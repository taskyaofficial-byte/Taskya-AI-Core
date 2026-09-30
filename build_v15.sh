#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/backend/app" "$ROOT/backend/app/tools" "$ROOT/backend/app/services" "$ROOT/backend/app/memory" "$ROOT/docker/sandbox" "$ROOT/browser" "$ROOT/uploads" "$ROOT/artifacts"
cat > "$ROOT/backend/requirements.txt" <<'EOF'
fastapi
uvicorn[standard]
python-dotenv
pydantic>=2
groq
tavily-python
python-multipart
pypdf
openpyxl
pandas
matplotlib
reportlab
passlib[bcrypt]
python-jose[cryptography]
playwright
EOF
cat > "$ROOT/backend/.env.example" <<'EOF'
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
GROQ_MODEL=openai/gpt-oss-120b
TASKYA_AI_MAX_STEPS=10
TASKYA_AI_WORKSPACE=workspace
TASKYA_AI_ARTIFACTS=artifacts
TASKYA_AI_UPLOADS=uploads
TASKYA_AI_DB=taskyaai.sqlite3
TASKYA_BROWSER_HEADLESS=true
TASKYA_BROWSER_ALLOWED_DOMAINS=*
TASKYA_DOCKER_ENABLED=true
TASKYA_DOCKER_IMAGE=python:3.11-slim
TASKYA_DOCKER_TIMEOUT=30
TASKYA_AUTH_SECRET=change-this-long-random-secret
TASKYA_ADMIN_EMAIL=admin@taskya.local
TASKYA_ADMIN_PASSWORD=change-this-password
TASKYA_PLAN_PRICE_INR=19
EOF
cat > "$ROOT/backend/app/config.py" <<'PY'
import os
from pathlib import Path
from dotenv import load_dotenv
BASE=Path(__file__).resolve().parents[2]
load_dotenv(BASE/'.env'); load_dotenv(BASE/'backend/.env')
GROQ_API_KEY=os.getenv('GROQ_API_KEY','').strip()
TAVILY_API_KEY=os.getenv('TAVILY_API_KEY','').strip()
GROQ_MODEL=os.getenv('GROQ_MODEL','openai/gpt-oss-120b').strip()
MAX_STEPS=int(os.getenv('TASKYA_AI_MAX_STEPS','10'))
WORKSPACE=(BASE/os.getenv('TASKYA_AI_WORKSPACE','workspace')).resolve()
ARTIFACTS=(BASE/os.getenv('TASKYA_AI_ARTIFACTS','artifacts')).resolve()
UPLOADS=(BASE/os.getenv('TASKYA_AI_UPLOADS','uploads')).resolve()
DB_PATH=(BASE/os.getenv('TASKYA_AI_DB','taskyaai.sqlite3')).resolve()
BROWSER_HEADLESS=os.getenv('TASKYA_BROWSER_HEADLESS','true').lower()=='true'
ALLOWED_DOMAINS=[x.strip().lower() for x in os.getenv('TASKYA_BROWSER_ALLOWED_DOMAINS','*').split(',') if x.strip()]
DOCKER_ENABLED=os.getenv('TASKYA_DOCKER_ENABLED','true').lower()=='true'
DOCKER_IMAGE=os.getenv('TASKYA_DOCKER_IMAGE','python:3.11-slim')
DOCKER_TIMEOUT=int(os.getenv('TASKYA_DOCKER_TIMEOUT','30'))
AUTH_SECRET=os.getenv('TASKYA_AUTH_SECRET','change-me')
ADMIN_EMAIL=os.getenv('TASKYA_ADMIN_EMAIL','admin@taskya.local')
ADMIN_PASSWORD=os.getenv('TASKYA_ADMIN_PASSWORD','change-me')
PLAN_PRICE_INR=int(os.getenv('TASKYA_PLAN_PRICE_INR','19'))
for p in (WORKSPACE,ARTIFACTS,UPLOADS): p.mkdir(parents=True,exist_ok=True)
PY
cat > "$ROOT/backend/app/memory/store.py" <<'PY'
import sqlite3,json
from datetime import datetime,timezone
class MemoryStore:
 def __init__(self,path):
  self.path=str(path)
  with sqlite3.connect(self.path) as c:
   c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_message TEXT,status TEXT,result TEXT,created_at TEXT,updated_at TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE,password_hash TEXT,created_at TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,plan TEXT,status TEXT,provider TEXT,provider_ref TEXT,created_at TEXT)')
 def now(self): return datetime.now(timezone.utc).isoformat()
 def task(self,i,m,status='queued'):
  n=self.now()
  with sqlite3.connect(self.path) as c:c.execute('INSERT OR REPLACE INTO tasks(id,user_message,status,result,created_at,updated_at) VALUES(?,?,?,?,?,?)',(i,m,status,None,n,n))
 def set_status(self,i,s,r=None):
  with sqlite3.connect(self.path) as c:c.execute('UPDATE tasks SET status=?,result=COALESCE(?,result),updated_at=? WHERE id=?',(s,r,self.now(),i))
 def event(self,i,t,p):
  with sqlite3.connect(self.path) as c:c.execute('INSERT INTO events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)',(i,t,json.dumps(p,ensure_ascii=False,default=str),self.now()))
 def get_task(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row;r=c.execute('SELECT * FROM tasks WHERE id=?',(i,)).fetchone()
   return dict(r) if r else None
 def events(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row
   return [dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY id',(i,)).fetchall()]
PY
cat > "$ROOT/backend/app/security/policy.py" <<'PY'
from enum import Enum
class Risk(str,Enum): LOW='low'; APPROVAL='approval_required'
SENSITIVE=('pay ','purchase','buy ','send email','send message','submit ','publish','book ','transfer ','delete ','destroy ','checkout','place order')
def classify(text):
 t=' '+text.lower().strip()
 return Risk.APPROVAL if any(x in t for x in SENSITIVE) else Risk.LOW
PY
cat > "$ROOT/backend/app/services/events.py" <<'PY'
import asyncio
class EventBus:
 def __init__(self): self.queues={}; self.cancelled=set()
 def create(self,tid): self.queues[tid]=asyncio.Queue(); self.cancelled.discard(tid)
 def emit(self,tid,event,payload=None):
  q=self.queues.get(tid)
  if q: q.put_nowait({'event':event,'task_id':tid,'data':payload or {}})
 def cancel(self,tid): self.cancelled.add(tid); self.emit(tid,'cancel_requested',{})
 def is_cancelled(self,tid): return tid in self.cancelled
 def close(self,tid): self.emit(tid,'done',{}); self.queues.pop(tid,None)
EVENTS=EventBus()
PY
cat > "$ROOT/backend/app/tools/calculator.py" <<'PY'
import ast,operator as op
A={ast.Add:op.add,ast.Sub:op.sub,ast.Mult:op.mul,ast.Div:op.truediv,ast.Mod:op.mod,ast.Pow:op.pow,ast.USub:op.neg,ast.UAdd:op.pos}
def ev(n):
 if isinstance(n,ast.Expression): return ev(n.body)
 if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
 if isinstance(n,ast.UnaryOp) and type(n.op) in A:return A[type(n.op)](ev(n.operand))
 if isinstance(n,ast.BinOp) and type(n.op) in A:
  b=ev(n.right)
  if isinstance(n.op,ast.Pow) and abs(b)>100: raise ValueError('Exponent too large')
  return A[type(n.op)](ev(n.left),b)
 raise ValueError('Unsupported expression')
def calculate(expression): return {'expression':expression,'result':ev(ast.parse(expression,mode='eval'))}
PY
cat > "$ROOT/backend/app/tools/search.py" <<'PY'
from ..config import TAVILY_API_KEY
def search_web(query,max_results=5):
 if not TAVILY_API_KEY:return {'error':'TAVILY_API_KEY is not configured'}
 from tavily import TavilyClient
 return TavilyClient(api_key=TAVILY_API_KEY).search(query=query,search_depth='advanced',max_results=max_results,include_answer=True)
PY
cat > "$ROOT/backend/app/tools/workspace.py" <<'PY'
from pathlib import Path
from ..config import WORKSPACE,ARTIFACTS

def safe(base,rel):
 p=(base/rel).resolve()
 if p!=base and base not in p.parents: raise ValueError('Path escapes allowed area')
 return p
def list_files(): return [str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob('*') if p.is_file()]
def read_file(path):
 p=safe(WORKSPACE,path)
 if not p.is_file(): return {'error':'File not found'}
 if p.stat().st_size>2_000_000:return {'error':'File too large'}
 return {'path':path,'content':p.read_text(encoding='utf-8')}
def write_artifact(filename,content):
 p=safe(ARTIFACTS,filename); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8')
 return {'created':str(p.relative_to(ARTIFACTS)),'bytes':len(content.encode())}
PY
cat > "$ROOT/backend/app/tools/browser.py" <<'PY'
import asyncio
from urllib.parse import urlparse
from ..config import BROWSER_HEADLESS,ALLOWED_DOMAINS

def allowed(url):
 host=(urlparse(url).hostname or '').lower()
 if not host:return False
 if '*' in ALLOWED_DOMAINS:return True
 return any(host==d or host.endswith('.'+d) for d in ALLOWED_DOMAINS)

def browse(url,action='inspect',selector='',text=''):
 if not allowed(url): return {'error':'Domain blocked by browser policy','url':url}
 try:
  from playwright.async_api import async_playwright
  async def run():
   async with async_playwright() as p:
    browser=await p.chromium.launch(headless=BROWSER_HEADLESS)
    page=await browser.new_page(viewport={'width':1440,'height':900})
    await page.goto(url,wait_until='domcontentloaded',timeout=30000)
    if action=='click' and selector: await page.locator(selector).first.click(timeout=10000)
    elif action=='fill' and selector: await page.locator(selector).first.fill(text,timeout=10000)
    await page.wait_for_timeout(500)
    title=await page.title(); body=(await page.locator('body').inner_text())[:12000]
    shot=await page.screenshot(type='png')
    await browser.close()
    import base64
    return {'url':page.url,'title':title,'text':body,'screenshot_base64':base64.b64encode(shot).decode()}
  return asyncio.run(run())
 except Exception as e:
  return {'error':str(e),'hint':'Run: playwright install chromium'}
PY
cat > "$ROOT/backend/app/tools/code_exec.py" <<'PY'
import json,subprocess,tempfile,os
from ..config import DOCKER_ENABLED,DOCKER_IMAGE,DOCKER_TIMEOUT

def run_python(code,timeout=None):
 if not DOCKER_ENABLED:return {'error':'Docker execution is disabled'}
 timeout=timeout or DOCKER_TIMEOUT
 if len(code)>100_000:return {'error':'Code too large'}
 with tempfile.TemporaryDirectory(prefix='taskya_') as d:
  fp=os.path.join(d,'main.py'); open(fp,'w',encoding='utf-8').write(code)
  cmd=['docker','run','--rm','--network','none','--cpus','1','--memory','512m','--pids-limit','128','-v',f'{d}:/work:rw','-w','/work',DOCKER_IMAGE,'python','main.py']
  try:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
   return {'returncode':p.returncode,'stdout':p.stdout[-12000:],'stderr':p.stderr[-12000:]}
  except subprocess.TimeoutExpired:return {'error':f'Code execution timed out after {timeout}s'}
  except FileNotFoundError:return {'error':'Docker CLI not found. Install Docker Desktop/Engine first.'}
PY
cat > "$ROOT/backend/app/tools/file_intel.py" <<'PY'
from pathlib import Path
from ..config import UPLOADS

def inspect_file(path):
 p=(UPLOADS/path).resolve()
 if UPLOADS not in p.parents or not p.is_file():return {'error':'File not found'}
 ext=p.suffix.lower()
 try:
  if ext=='.pdf':
   from pypdf import PdfReader
   r=PdfReader(str(p)); text='\n'.join((x.extract_text() or '') for x in r.pages)
   return {'type':'pdf','pages':len(r.pages),'text':text[:50000]}
  if ext in ('.xlsx','.xlsm'):
   from openpyxl import load_workbook
   wb=load_workbook(p,read_only=True,data_only=True); out={}
   for ws in wb.worksheets:
    rows=[]
    for row in ws.iter_rows(values_only=True): rows.append(list(row))
    out[ws.title]=rows[:500]
   return {'type':'excel','sheets':out}
  if ext=='.csv':
   import pandas as pd
   df=pd.read_csv(p); return {'type':'csv','rows':len(df),'columns':list(df.columns),'preview':df.head(50).to_dict(orient='records')}
  if ext in ('.txt','.md','.json','.html','.htm'):
   return {'type':'text','text':p.read_text(encoding='utf-8')[:50000]}
  return {'error':'Unsupported file type'}
 except Exception as e:return {'error':str(e)}
PY
cat > "$ROOT/backend/app/tools/registry.py" <<'PY'
from .calculator import calculate
from .search import search_web
from .workspace import list_files,read_file,write_artifact
from .browser import browse
from .code_exec import run_python
from .file_intel import inspect_file
TOOLS={
'calculate':{'description':'Safely calculate arithmetic.','parameters':{'type':'object','properties':{'expression':{'type':'string'}},'required':['expression']},'fn':calculate},
'search_web':{'description':'Search the live web for current information.','parameters':{'type':'object','properties':{'query':{'type':'string'},'max_results':{'type':'integer'}},'required':['query']},'fn':search_web},
'list_files':{'description':'List safe workspace files.','parameters':{'type':'object','properties':{}},'fn':list_files},
'read_file':{'description':'Read a UTF-8 workspace file.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},'fn':read_file},
'write_artifact':{'description':'Create a text, HTML, CSV or JSON artifact.','parameters':{'type':'object','properties':{'filename':{'type':'string'},'content':{'type':'string'}},'required':['filename','content']},'fn':write_artifact},
'browse':{'description':'Open a webpage, inspect DOM text and screenshot it; can click/fill non-consequential controls.','parameters':{'type':'object','properties':{'url':{'type':'string'},'action':{'type':'string','enum':['inspect','click','fill']},'selector':{'type':'string'},'text':{'type':'string'}},'required':['url']},'fn':browse},
'run_python':{'description':'Run Python in an isolated Docker sandbox with no network.','parameters':{'type':'object','properties':{'code':{'type':'string'},'timeout':{'type':'integer'}},'required':['code']},'fn':run_python},
'inspect_file':{'description':'Extract useful text/data from uploaded PDF, Excel, CSV and text files.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']},'fn':inspect_file}}
def schemas():return [{'type':'function','function':{'name':n,'description':x['description'],'parameters':x['parameters']}} for n,x in TOOLS.items()]
PY
cat > "$ROOT/backend/app/providers/groq_agent.py" <<'PY'
import json,uuid
from groq import Groq
from ..config import GROQ_API_KEY,GROQ_MODEL,MAX_STEPS
from ..tools.registry import TOOLS,schemas
from ..security.policy import classify,Risk
from ..services.events import EVENTS
SYSTEM='''You are Taskya AI, an India-first autonomous AI agent. Understand Hindi, Hinglish, English and natural Indian code-mixed conversation. Accomplish the user's real goal instead of merely chatting. Use a ReAct-style loop: plan the next useful action, call a tool, inspect its result, re-plan, and verify before finishing. Use live web search when current external information is needed. Use browser inspection for websites, Docker Python for computation/data work, and file intelligence for uploaded documents. Never claim an action succeeded without evidence. If a tool fails, diagnose and try a safe alternative. Consequential actions such as payment, purchase, sending, publishing, booking, transfers or destructive changes require human approval and must not be executed merely because a user asks. Keep answers in the user's requested language.''' 
class TaskyaAgent:
 def __init__(self,memory):
  self.client=Groq(api_key=GROQ_API_KEY); self.memory=memory
 def run(self,user_message,language='auto',task_id=None,approved=False):
  task_id=task_id or str(uuid.uuid4()); self.memory.task(task_id,user_message,'running'); EVENTS.emit(task_id,'planning',{'message':'Taskya is planning the task'})
  if classify(user_message)==Risk.APPROVAL and not approved:
   msg='यह task consequential action मांग रहा है। पहले human approval जरूरी है। मैं planning/research कर सकता हूँ, लेकिन payment/send/publish/book/transfer/delete जैसी action बिना approval execute नहीं करूंगा।'
   self.memory.set_status(task_id,'approval_required',msg); EVENTS.emit(task_id,'approval_required',{'reason':'consequential_action'}); return {'task_id':task_id,'status':'approval_required','answer':msg}
  msgs=[{'role':'system','content':SYSTEM+'\nPreferred response language: '+language},{'role':'user','content':user_message}]
  for step in range(1,MAX_STEPS+1):
   if EVENTS.is_cancelled(task_id): self.memory.set_status(task_id,'cancelled','Task cancelled by user.'); return {'task_id':task_id,'status':'cancelled','answer':'Task cancelled.'}
   EVENTS.emit(task_id,'step',{'step':step,'status':'thinking'}); self.memory.event(task_id,'agent_step',{'step':step})
   try:r=self.client.chat.completions.create(model=GROQ_MODEL,messages=msgs,tools=schemas(),tool_choice='auto',parallel_tool_calls=False,temperature=0.2)
   except Exception as e:
    self.memory.set_status(task_id,'failed',str(e)); EVENTS.emit(task_id,'error',{'error':str(e)}); return {'task_id':task_id,'status':'failed','answer':str(e)}
   m=r.choices[0].message; calls=m.tool_calls or []
   if not calls:
    ans=m.content or 'No final answer.'; self.memory.set_status(task_id,'completed',ans); EVENTS.emit(task_id,'completed',{'answer':ans}); return {'task_id':task_id,'status':'completed','answer':ans,'steps':step}
   msgs.append({'role':'assistant','content':m.content or '', 'tool_calls':[{'id':c.id,'type':'function','function':{'name':c.function.name,'arguments':c.function.arguments}} for c in calls]})
   for c in calls:
    EVENTS.emit(task_id,'tool_start',{'tool':c.function.name});
    try:args=json.loads(c.function.arguments or '{}'); res=TOOLS[c.function.name]['fn'](**args)
    except Exception as e:res={'error':str(e),'tool':getattr(c.function,'name','unknown')}
    self.memory.event(task_id,'tool_result',{'tool':c.function.name,'result':res}); EVENTS.emit(task_id,'tool_result',{'tool':c.function.name,'result_preview':str(res)[:1200]})
    msgs.append({'role':'tool','tool_call_id':c.id,'content':json.dumps(res,ensure_ascii=False,default=str)})
  ans='Maximum execution steps reached; task is not verified as complete.'; self.memory.set_status(task_id,'incomplete',ans); EVENTS.emit(task_id,'incomplete',{}); return {'task_id':task_id,'status':'incomplete','answer':ans,'steps':MAX_STEPS}
PY
cat > "$ROOT/backend/app/auth.py" <<'PY'
import base64,hmac,hashlib,json,time
from passlib.context import CryptContext
from .config import AUTH_SECRET,ADMIN_EMAIL,ADMIN_PASSWORD
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
def token(email):
 payload={'sub':email,'exp':int(time.time())+86400*7}; raw=base64.urlsafe_b64encode(json.dumps(payload,separators=(',',':')).encode()).decode().rstrip('='); sig=hmac.new(AUTH_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest(); return raw+'.'+sig
def verify(t):
 try:
  raw,sig=t.split('.',1); good=hmac.compare_digest(sig,hmac.new(AUTH_SECRET.encode(),raw.encode(),hashlib.sha256).hexdigest()); p=json.loads(base64.urlsafe_b64decode(raw+'='*((4-len(raw)%4)%4))); return p['sub'] if good and p['exp']>time.time() else None
 except Exception:return None
def check_login(email,password):return hmac.compare_digest(email,ADMIN_EMAIL) and hmac.compare_digest(password,ADMIN_PASSWORD)
PY
cat > "$ROOT/backend/app/api.py" <<'PY'
import asyncio,json,uuid
from fastapi import APIRouter,UploadFile,File,HTTPException,Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from .config import DB_PATH,UPLOADS,PLAN_PRICE_INR
from .memory.store import MemoryStore
from .providers.groq_agent import TaskyaAgent
from .services.events import EVENTS
from .auth import check_login,token,verify
router=APIRouter(); memory=MemoryStore(DB_PATH); agent=TaskyaAgent(memory)
class Task(BaseModel): message:str=Field(min_length=1,max_length=20000); language:str=Field(default='auto',max_length=30)
class Login(BaseModel): email:str; password:str
class Approval(BaseModel): approved:bool

def auth(h):
 if not h or not h.lower().startswith('bearer '):raise HTTPException(401,'Authentication required')
 e=verify(h.split(' ',1)[1]);
 if not e:raise HTTPException(401,'Invalid or expired token')
 return e
@router.post('/auth/login')
def login(x:Login):
 if not check_login(x.email,x.password):raise HTTPException(401,'Invalid credentials')
 return {'access_token':token(x.email),'token_type':'bearer'}
async def worker(tid,x,approved=False):
 EVENTS.create(tid)
 try: await asyncio.to_thread(agent.run,x.message,x.language,tid,approved)
 finally: EVENTS.close(tid)
@router.post('/task')
async def task(x:Task):
 tid=str(uuid.uuid4()); memory.task(tid,x.message,'queued'); EVENTS.create(tid); asyncio.create_task(worker(tid,x)); return {'task_id':tid,'status':'queued'}
@router.get('/task/{tid}')
def status(tid):
 t=memory.get_task(tid)
 if not t:raise HTTPException(404,'Task not found')
 return t
@router.get('/task/{tid}/events')
async def events(tid):
 if not memory.get_task(tid):raise HTTPException(404,'Task not found')
 q=EVENTS.queues.setdefault(tid,asyncio.Queue())
 async def gen():
  sent=0
  for e in memory.events(tid): yield 'data: '+json.dumps({'event':e['event_type'],'data':json.loads(e['payload'])},ensure_ascii=False)+'\n\n'; sent+=1
  while True:
   e=await q.get(); yield 'data: '+json.dumps(e,ensure_ascii=False)+'\n\n'
   if e['event']=='done':break
 return StreamingResponse(gen(),media_type='text/event-stream')
@router.post('/task/{tid}/cancel')
def cancel(tid):
 if not memory.get_task(tid):raise HTTPException(404,'Task not found')
 EVENTS.cancel(tid); memory.set_status(tid,'cancelling'); return {'status':'cancelling'}
@router.post('/task/{tid}/approve')
async def approve(tid,x:Approval):
 t=memory.get_task(tid)
 if not t:raise HTTPException(404,'Task not found')
 if not x.approved:return {'status':'approval_rejected'}
 return await _resume(tid,t)
async def _resume(tid,t):
 x=Task(message=t['user_message'],language='auto'); memory.set_status(tid,'running'); EVENTS.create(tid); asyncio.create_task(worker(tid,x,True)); return {'task_id':tid,'status':'resumed'}
@router.post('/upload')
async def upload(file:UploadFile=File(...)):
 name=PathSafe(file.filename or 'upload.bin'); dest=UPLOADS/name; data=await file.read()
 if len(data)>25_000_000:raise HTTPException(413,'File too large (25MB max)')
 dest.write_bytes(data); return {'filename':name,'bytes':len(data)}
def PathSafe(name):
 import re; return re.sub(r'[^A-Za-z0-9._-]','_',name)[:180]
@router.get('/billing/plan')
def plan():return {'plan':'Taskya AI Pro','price_inr':PLAN_PRICE_INR,'currency':'INR','status':'configuration_only','message':'Connect Razorpay/Cashfree credentials and webhook before taking real payments.'}
PY
# fix imports and create init files
for f in backend/app/__init__.py backend/app/security/__init__.py backend/app/services/__init__.py backend/app/memory/__init__.py backend/app/providers/__init__.py backend/app/tools/__init__.py; do touch "$ROOT/$f"; done
cat > "$ROOT/backend/app/main.py" <<'PY'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
app=FastAPI(title='Taskya AI',version='1.5.0',description='India-first autonomous AI agent')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
@app.get('/')
def health():return {'name':'Taskya AI','status':'online','version':'1.5.0','mode':'plan-act-observe-verify'}
app.include_router(router,prefix='/api')
PY
cat > "$ROOT/frontend/index.html" <<'HTML'
<!doctype html><html lang="hi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Taskya AI</title><link rel="stylesheet" href="style.css"></head><body><main><header><div><h1>Taskya AI</h1><p>सोचो → करो → जाँचो → पूरा करो</p></div><label>भाषा <select id="lang"><option value="auto">Auto</option><option value="hi">हिन्दी</option><option value="hinglish">Hinglish</option><option value="en">English</option><option value="bn">বাংলা</option><option value="mr">मराठी</option><option value="ta">தமிழ்</option><option value="te">తెలుగు</option></select></label></header><section id="chat"><div id="welcome"><h2>आज Taskya से क्या काम करवाना है?</h2><p>Research, websites, files, Excel/PDF, calculations और multi-step tasks लिखें या बोलें.</p></div></section><div class="progress"><div id="events">Ready</div><button id="cancel" disabled>Cancel Task</button></div><form id="f"><textarea id="i" placeholder="उदाहरण: India में AI agent market की current research करो और summary बनाओ..."></textarea><div class="actions"><button type="button" id="mic">🎤 Voice</button><button type="button" id="speak">🔊 Read</button><button>Run Task</button></div></form><input id="file" type="file"><p id="voiceStatus"></p></main><script src="app.js"></script></body></html>
HTML
cat > "$ROOT/frontend/app.js" <<'JS'
const base='http://127.0.0.1:8000/api';const chat=document.getElementById('chat'),form=document.getElementById('f'),input=document.getElementById('i'),lang=document.getElementById('lang'),mic=document.getElementById('mic'),events=document.getElementById('events'),cancel=document.getElementById('cancel'),file=document.getElementById('file'),voiceStatus=document.getElementById('voiceStatus');let current=null,lastAnswer='';
function add(t,c){const e=document.createElement('div');e.className='m '+c;e.textContent=t;chat.appendChild(e);chat.scrollTop=chat.scrollHeight;return e}
async function watch(id){const es=new EventSource(`${base}/task/${id}/events`);es.onmessage=e=>{const d=JSON.parse(e.data);events.textContent=d.event+(d.data?.tool?` • ${d.data.tool}`:'');if(d.event==='completed'){lastAnswer=d.data.answer||'';add(lastAnswer,'a')}if(d.event==='approval_required'){add('⚠️ Human approval required. Use the API approval endpoint after reviewing the action.','a')}if(['done','completed','failed','cancelled'].includes(d.event)){} };es.onerror=()=>es.close();}
form.onsubmit=async e=>{e.preventDefault();const t=input.value.trim();if(!t)return;document.getElementById('welcome')?.remove();add(t,'u');input.value='';events.textContent='Submitting…';try{const r=await fetch(base+'/task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t,language:lang.value})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');current=d.task_id;cancel.disabled=false;watch(current);}catch(x){add('Backend connection/error: '+x.message,'a')}};
cancel.onclick=async()=>{if(!current)return;await fetch(`${base}/task/${current}/cancel`,{method:'POST'});events.textContent='Cancellation requested';cancel.disabled=true};
document.getElementById('speak').onclick=()=>{if(!lastAnswer)return;window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(lastAnswer);u.lang=lang.value==='en'?'en-IN':'hi-IN';speechSynthesis.speak(u)};
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){mic.disabled=true;mic.textContent='🎤 Voice unavailable'}else{const rec=new SR();rec.interimResults=true;rec.continuous=false;mic.onclick=()=>{rec.lang=lang.value==='en'?'en-IN':'hi-IN';voiceStatus.textContent='🎤 सुन रहा हूँ…';rec.start()};rec.onresult=e=>input.value=Array.from(e.results).map(r=>r[0].transcript).join('');rec.onend=()=>voiceStatus.textContent='';rec.onerror=e=>voiceStatus.textContent='Voice error: '+e.error}
file.onchange=async()=>{if(!file.files[0])return;const fd=new FormData();fd.append('file',file.files[0]);const r=await fetch(base+'/upload',{method:'POST',body:fd});const d=await r.json();input.value+=(input.value?'\n':'')+`Uploaded file: ${d.filename}. Use inspect_file to analyze it.`};
JS
cat > "$ROOT/frontend/style.css" <<'CSS'
*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#eef2ff;font-family:system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:900px;margin:auto;padding:24px}header{display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid #28314f;padding-bottom:18px}h1{margin:0;font-size:32px}header p{margin:6px 0;color:#9ca8c7}select,textarea,button,input[type=file]{border:1px solid #34405f;border-radius:10px;background:#111a30;color:#eef2ff;padding:10px}#chat{height:55vh;overflow:auto;padding:18px 0}.m{max-width:85%;padding:12px 15px;border-radius:14px;margin:10px 0;white-space:pre-wrap}.u{margin-left:auto;background:#26365d}.a{background:#151f36}.progress{display:flex;justify-content:space-between;align-items:center;color:#9ca8c7;margin:8px 0}textarea{width:100%;min-height:100px;resize:vertical}.actions{display:flex;gap:10px;margin-top:10px}.actions button:last-child{margin-left:auto}.progress button{font-size:12px}#voiceStatus{min-height:20px;color:#9ca8c7}
CSS
cat > "$ROOT/docker/sandbox/Dockerfile" <<'EOF'
FROM python:3.11-slim
RUN useradd -m runner
USER runner
WORKDIR /work
RUN pip install --no-cache-dir pandas openpyxl matplotlib reportlab pypdf
ENTRYPOINT ["python"]
EOF
cat > "$ROOT/docker/README.md" <<'EOF'
# Taskya AI Docker Sandbox
The agent can execute Python through Docker with `--network none`, CPU/memory/PID limits and a temporary mounted work directory. This requires Docker Desktop/Engine on the host.
EOF
cat > "$ROOT/browser/README.md" <<'EOF'
# Taskya AI Browser Worker
V1.5 uses Playwright for isolated browser sessions. Install Chromium once:
`python -m playwright install chromium`
The browser tool supports inspect/click/fill, screenshots and DOM text. Consequential actions remain subject to approval policy.
EOF
cat > "$ROOT/docs/ARCHITECTURE.md" <<'EOF'
# Taskya AI V1.5 Architecture
User → FastAPI Task API → Background Agent Worker → Groq tool-calling loop → Tools → Observe → Re-plan → Verify.
Tools: Tavily search, Playwright browser, Docker Python sandbox, PDF/Excel/CSV/text inspection, workspace/artifacts.
Control plane: SQLite task state, SSE events, cancel endpoint, approval gate and resumable approval flow.
Frontend: live event display, browser STT, browser TTS, language selector, upload.
Security boundaries: workspace path jail, browser domain policy, Docker network disabled + resource limits, approval gate for consequential intent.
Production next: Redis/Celery or a managed queue, PostgreSQL, object storage, reverse proxy, HTTPS, per-user quotas, secret manager, real payment provider + webhook, stronger browser isolation and observability.
EOF
cat > "$ROOT/docs/ROADMAP.md" <<'EOF'
# Taskya AI Roadmap
## V1.5 included
- Browser Worker / Playwright
- Docker Python sandbox
- Live SSE task events
- Screenshot/DOM text capture
- Multi-step tool loop + retry-safe failure handling
- PDF/Excel/CSV/text inspection
- Browser STT + TTS
- Human approval gate
- Task cancellation and approval resume
- Local authentication foundation
- Billing plan metadata foundation
## Production hardening
- Redis/Postgres workers
- real OAuth/SSO
- Razorpay/Cashfree production checkout + signed webhooks
- per-user quotas and rate limits
- durable browser profiles with secret isolation
- OCR worker and image understanding
- mobile/WhatsApp connectors
EOF
cat > "$ROOT/README.md" <<'EOF'
# Taskya AI V1.5 — Autonomous Agent Core
India-first AI agent foundation focused on real task execution.

## Included
- Groq tool-calling ReAct loop
- Tavily live search
- Playwright browser worker: DOM text + screenshot + inspect/click/fill
- Docker Python sandbox: no network + CPU/memory/PID limits
- PDF/Excel/CSV/text file intelligence
- Artifact/workspace tools
- Live Server-Sent Events (SSE) task progress
- Cancel + approval/resume flow
- Browser Speech-to-Text and SpeechSynthesis text-to-speech
- Hindi/Hinglish/English/regional language selector
- Local authentication foundation
- Billing plan metadata (real payment credentials/webhook still required)

## Local setup (Windows)
1. Install Python 3.11+ and Docker Desktop.
2. Copy `.env.example` to `.env` and add Groq/Tavily keys.
3. `python -m venv .venv`
4. `.venv\\Scripts\\activate`
5. `pip install -r backend\\requirements.txt`
6. `python -m playwright install chromium`
7. `uvicorn backend.app.main:app --reload --port 8000`
8. Open `frontend/index.html`.

## Linux/macOS
`python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt && python -m playwright install chromium && uvicorn backend.app.main:app --reload --port 8000`

## Reality check
This is a substantially more complete agent core, but it is not a finished cloud product or a proven Manus replacement. Production authentication, payment processing, multi-tenant isolation, durable workers and stronger browser security still require deployment infrastructure and credentials.
EOF
# smoke tests
cat > "$ROOT/tests/test_smoke.py" <<'PY'
def test_imports():
 from backend.app.tools.registry import TOOLS
 assert {'calculate','search_web','browse','run_python','inspect_file'}.issubset(TOOLS)
PY
cd "$ROOT" && rm -f Taskya-AI-Core-V1.5.zip && cd .. && zip -qr Taskya-AI-Core-V1.5.zip Taskya-AI-Core
ls -lh /mnt/data/taskya_build/../Taskya-AI-Core-V1.5.zip
