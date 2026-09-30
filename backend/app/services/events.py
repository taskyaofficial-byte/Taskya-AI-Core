import asyncio
class EventBus:
 def __init__(self): self.queues={};self.cancelled=set()
 def create(self,tid): self.queues[tid]=asyncio.Queue();self.cancelled.discard(tid)
 def emit(self,tid,event,payload=None):
  q=self.queues.get(tid)
  if q:q.put_nowait({'event':event,'task_id':tid,'data':payload or {}})
 def cancel(self,tid): self.cancelled.add(tid);self.emit(tid,'cancel_requested',{})
 def is_cancelled(self,tid): return tid in self.cancelled
 def close(self,tid): self.emit(tid,'done',{})
EVENTS=EventBus()
