import asyncio,json,uuid,re
from fastapi import APIRouter,UploadFile,File,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from .config import DB_PATH,UPLOADS,PLAN_PRICE_INR,GROQ_MODEL,GROQ_FALLBACK_MODEL
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
history: list[dict] = Field(default_factory=list)
@router.post('/chat')
async def chat(x:ChatRequest):
 # Compatibility endpoint for simple frontends that expect POST /api/chat.
 result=await asyncio.to_thread(agent.run,x.message,x.language,None,False,x.web_enabled,x.history)
 return {
  'answer': result.get('answer',''),
  'response': result.get('answer',''),
  'status': result.get('status','unknown'),
  'task_id': result.get('task_id'),
  'plan': result.get('plan'),
  'metrics': result.get('metrics')
 }

@router.get('/health')
def api_health():
 return {'status':'ok','service':'Taskya AI API','chat_endpoint':'/api/chat','task_endpoint':'/api/task','groq_model':GROQ_MODEL,'fallback_model':GROQ_FALLBACK_MODEL}

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


# Optional Razorpay checkout endpoints. Credentials stay server-side in Render env vars.
try:
 from .config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
 import razorpay
except Exception:
 RAZORPAY_KEY_ID=''; RAZORPAY_KEY_SECRET=''; razorpay=None

class BillingRequest(BaseModel):
 amount_inr:int=Field(default=19,ge=1,le=100000)

@router.post('/billing/create-order')
def create_billing_order(x:BillingRequest):
 if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET or razorpay is None:
  raise HTTPException(503,'Razorpay is not configured on the backend')
 try:
  client=razorpay.Client(auth=(RAZORPAY_KEY_ID,RAZORPAY_KEY_SECRET))
  order=client.order.create({'amount':x.amount_inr*100,'currency':'INR','receipt':'taskya-'+uuid.uuid4().hex[:20],'payment_capture':1})
  return {'order_id':order['id'],'amount':order['amount'],'currency':order['currency'],'key_id':RAZORPAY_KEY_ID}
 except Exception:
  raise HTTPException(502,'Unable to create payment order')

class BillingVerify(BaseModel):
 razorpay_payment_id:str
 razorpay_order_id:str
 razorpay_signature:str

@router.post('/billing/verify')
def verify_billing(x:BillingVerify):
 if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET or razorpay is None:
  raise HTTPException(503,'Razorpay is not configured on the backend')
 try:
  client=razorpay.Client(auth=(RAZORPAY_KEY_ID,RAZORPAY_KEY_SECRET))
  client.utility.verify_payment_signature({'razorpay_order_id':x.razorpay_order_id,'razorpay_payment_id':x.razorpay_payment_id,'razorpay_signature':x.razorpay_signature})
  return {'status':'verified'}
 except Exception:
  raise HTTPException(400,'Payment signature verification failed')
