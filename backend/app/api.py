import asyncio,json,uuid,re
from fastapi import APIRouter,UploadFile,File,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from .config import DB_PATH,UPLOADS,PLAN_PRICE_INR
from .memory.store import MemoryStore
from .providers.groq_agent import TaskyaAgent
from .services.events import EVENTS
router=APIRouter();memory=MemoryStore(DB_PATH);agent=TaskyaAgent(memory)
class Task(BaseModel):message:str=Field(min_length=1,max_length=20000);language:str='auto';web_enabled:bool=False
class Approval(BaseModel):approved:bool
async def worker(tid,x,approved=False):
 try:await asyncio.to_thread(agent.run,x.message,x.language,tid,approved,x.web_enabled)
 finally:EVENTS.close(tid)

class ChatRequest(BaseModel):
 message:str=Field(min_length=1,max_length=20000)
 language:str='auto'
 web_enabled:bool=False

@router.post('/chat')
async def chat(x:ChatRequest):
 # Compatibility endpoint for simple frontends that expect POST /api/chat.
 result=await asyncio.to_thread(agent.run,x.message,x.language,None,False,x.web_enabled)
 return {
  'answer': result.get('answer',''),
  'response': result.get('answer',''),
  'status': result.get('status','unknown'),
  'task_id': result.get('task_id')
 }

@router.get('/health')
def api_health():
 return {'status':'ok','service':'Taskya AI API','chat_endpoint':'/api/chat','task_endpoint':'/api/task'}

@router.post('/task')
async def task(x:Task):
 tid=str(uuid.uuid4());memory.task(tid,x.message,'queued');EVENTS.create(tid);asyncio.create_task(worker(tid,x));return {'task_id':tid,'status':'queued'}
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
  for e in memory.events(tid):yield 'data: '+json.dumps({'event':e['event_type'],'data':json.loads(e['payload'])},ensure_ascii=False)+'\n\n'
  while True:
   e=await q.get();yield 'data: '+json.dumps(e,ensure_ascii=False)+'\n\n'
   if e['event']=='done':break
 return StreamingResponse(gen(),media_type='text/event-stream')
@router.post('/task/{tid}/cancel')
def cancel(tid):
 if not memory.get_task(tid):raise HTTPException(404,'Task not found')
 EVENTS.cancel(tid);memory.set_status(tid,'cancelling');return {'status':'cancelling'}
@router.post('/task/{tid}/approve')
async def approve(tid,x:Approval):
 t=memory.get_task(tid)
 if not t:raise HTTPException(404,'Task not found')
 if not x.approved:return {'status':'approval_rejected'}
 memory.set_status(tid,'running');EVENTS.create(tid);asyncio.create_task(worker(tid,Task(message=t['user_message'],language='auto',web_enabled=False),True));return {'task_id':tid,'status':'resumed'}
@router.post('/upload')
async def upload(file:UploadFile=File(...)):
 name=re.sub(r'[^A-Za-z0-9._-]','_',file.filename or 'upload.bin')[:180];data=await file.read()
 if len(data)>25000000:raise HTTPException(413,'File too large')
 (UPLOADS/name).write_bytes(data);return {'filename':name,'bytes':len(data)}
@router.get('/billing/plan')
def plan():return {'plan':'Taskya AI Pro','price_inr':PLAN_PRICE_INR,'currency':'INR','status':'configuration_only','message':'Real payment provider and webhook credentials are required before charging users.'}
