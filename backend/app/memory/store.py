import sqlite3,json
from datetime import datetime,timezone
class MemoryStore:
 def __init__(self,path):
  self.path=str(path)
  with sqlite3.connect(self.path) as c:
   c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_message TEXT,status TEXT,result TEXT,created_at TEXT,updated_at TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)')
 def now(self): return datetime.now(timezone.utc).isoformat()
 def task(self,i,m,status='queued'):
  n=self.now()
  with sqlite3.connect(self.path) as c:c.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?)',(i,m,status,None,n,n))
 def set_status(self,i,s,r=None):
  with sqlite3.connect(self.path) as c:c.execute('UPDATE tasks SET status=?,result=COALESCE(?,result),updated_at=? WHERE id=?',(s,r,self.now(),i))
 def event(self,i,t,p):
  with sqlite3.connect(self.path) as c:c.execute('INSERT INTO events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)',(i,t,json.dumps(p,ensure_ascii=False,default=str),self.now()))
 def get_task(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row;r=c.execute('SELECT * FROM tasks WHERE id=?',(i,)).fetchone();return dict(r) if r else None
 def events(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row;return [dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY id',(i,)).fetchall()]
