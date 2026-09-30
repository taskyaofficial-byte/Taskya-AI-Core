import asyncio,json,uuid,re,os,hmac,hashlib,base64,urllib.request,urllib.error
from fastapi import APIRouter,UploadFile,File,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from .config import DB_PATH,UPLOADS,PLAN_PRICE_INR,GROQ_MODEL,GROQ_FALLBACK_MODEL,RAZORPAY_KEY_ID,RAZORPAY_KEY_SECRET
from .memory.store import MemoryStore
from .providers.groq_agent import TaskyaAgent
from .services.events import EVENTS
router=APIRouter();memory=MemoryStore(DB_PATH);agent=TaskyaAgent(memory)
class Task(BaseModel):message:str=Field(min_length=1,max_length=20000);language:str='auto';web_enabled:bool=False;session_id:str=Field(default='',max_length=128)
class Approval(BaseModel):approved:bool
async def worker(tid,x,approved=False):
 try:await asyncio.to_thread(agent.run,x.message,x.language,tid,approved,x.web_enabled,x.session_id)
 finally:EVENTS.close(tid)
class ChatRequest(BaseModel):
 message:str=Field(min_length=1,max_length=20000);language:str='auto';web_enabled:bool=False;session_id:str=Field(default='',max_length=128)
class PaymentOrder(BaseModel):
 session_id:str=Field(default='',max_length=128)
class PaymentVerify(BaseModel):
 razorpay_order_id:str;razorpay_payment_id:str;razorpay_signature:str;session_id:str=Field(default='',max_length=128)

def _razorpay_request(path,payload):
 if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET: raise HTTPException(503,'Payment gateway is not configured yet. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in Render.')
 body=json.dumps(payload).encode();token=base64.b64encode(f'{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}'.encode()).decode()
 req=urllib.request.Request('https://api.razorpay.com/v1/'+path,data=body,headers={'Authorization':'Basic '+token,'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())
 except urllib.error.HTTPError as e:
  detail=e.read().decode(errors='ignore')
  raise HTTPException(502,'Payment gateway error: '+detail[:600])
 except Exception as e: raise HTTPException(502,'Payment gateway connection failed: '+str(e))

@router.post('/chat')
async def chat(x:ChatRequest):
 result=await asyncio.to_thread(agent.run,x.message,x.language,None,False,x.web_enabled,x.session_id)
 return {'answer':result.get('answer',''),'response':result.get('answer',''),'status':result.get('status','unknown'),'task_id':result.get('task_id')}

@router.get('/health')
def api_health():
 return {'status':'ok','service':'Taskya AI API','chat_endpoint':'/api/chat','task_endpoint':'/api/task','groq_model':GROQ_MODEL,'fallback_model':GROQ_FALLBACK_MODEL,'payment_gateway':bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)}

@router.post('/task')
async def task(x:Task):
 tid=str(uuid.uuid4());memory.task(tid,x.message,'queued',x.session_id or None);EVENTS.create(tid);asyncio.create_task(worker(tid,x));return {'task_id':tid,'status':'queued'}

@router.get('/history')
def history(session_id:str,limit:int=50):
 if not session_id: raise HTTPException(400,'session_id is required')
 return {'items':memory.list_tasks(session_id,max(1,min(limit,100)))}

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
 memory.set_status(tid,'running');EVENTS.create(tid);asyncio.create_task(worker(tid,Task(message=t['user_message'],language='auto',web_enabled=False,session_id=t.get('session_id') or ''),True));return {'task_id':tid,'status':'resumed'}
@router.post('/upload')
async def upload(file:UploadFile=File(...)):
 name=re.sub(r'[^A-Za-z0-9._-]','_',file.filename or 'upload.bin')[:180];data=await file.read()
 if len(data)>25000000:raise HTTPException(413,'File too large')
 (UPLOADS/name).write_bytes(data);return {'filename':name,'bytes':len(data)}

@router.get('/billing/plan')
def plan():
 return {'plan':'Taskya AI Pro','price_inr':PLAN_PRICE_INR,'currency':'INR','gateway':'razorpay','configured':bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET),'message':'Add Razorpay credentials in Render to activate live checkout.'}

@router.post('/billing/order')
def billing_order(x:PaymentOrder):
 receipt='taskya_'+uuid.uuid4().hex[:20]
 order=_razorpay_request('orders',{'amount':PLAN_PRICE_INR*100,'currency':'INR','receipt':receipt,'notes':{'product':'Taskya AI Pro','session_id':x.session_id[:128]}})
 return {'key_id':RAZORPAY_KEY_ID,'order_id':order['id'],'amount':order['amount'],'currency':order['currency'],'name':'Taskya AI','description':f'Taskya AI Pro - ₹{PLAN_PRICE_INR}','prefill':{'email':os.getenv('TASKYA_CONTACT_EMAIL','info@taskya.in')}}

@router.post('/billing/verify')
def billing_verify(x:PaymentVerify):
 msg=f'{x.razorpay_order_id}|{x.razorpay_payment_id}'.encode()
 expected=hmac.new(RAZORPAY_KEY_SECRET.encode(),msg,hashlib.sha256).hexdigest()
 if not hmac.compare_digest(expected,x.razorpay_signature):raise HTTPException(400,'Payment signature verification failed')
 return {'status':'paid','message':'Payment verified successfully.','payment_id':x.razorpay_payment_id,'order_id':x.razorpay_order_id}
