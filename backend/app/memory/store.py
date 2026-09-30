import sqlite3,json
from datetime import datetime,timezone

class MemoryStore:
 def __init__(self,path):
  self.path=str(path)
  with sqlite3.connect(self.path) as c:
   c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_message TEXT,status TEXT,result TEXT,created_at TEXT,updated_at TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)')
   cols={r[1] for r in c.execute('PRAGMA table_info(tasks)').fetchall()}
   if 'session_id' not in cols:
    c.execute('ALTER TABLE tasks ADD COLUMN session_id TEXT')
   c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_session_updated ON tasks(session_id,updated_at DESC)')
 def now(self): return datetime.now(timezone.utc).isoformat()
 def task(self,i,m,status='queued',session_id=None):
  n=self.now()
  with sqlite3.connect(self.path) as c:
   c.execute('INSERT OR REPLACE INTO tasks(id,user_message,status,result,created_at,updated_at,session_id) VALUES(?,?,?,?,?,?,?)',(i,m,status,None,n,n,session_id))
 def set_status(self,i,s,r=None):
  with sqlite3.connect(self.path) as c:c.execute('UPDATE tasks SET status=?,result=COALESCE(?,result),updated_at=? WHERE id=?',(s,r,self.now(),i))
 def event(self,i,t,p):
  with sqlite3.connect(self.path) as c:c.execute('INSERT INTO events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)',(i,t,json.dumps(p,ensure_ascii=False,default=str),self.now()))
 def get_task(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row;r=c.execute('SELECT * FROM tasks WHERE id=?',(i,)).fetchone();return dict(r) if r else None
 def list_tasks(self,session_id,limit=50):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row
   rows=c.execute('SELECT id,user_message,status,result,created_at,updated_at FROM tasks WHERE session_id=? ORDER BY updated_at DESC LIMIT ?',(session_id,limit)).fetchall()
   return [dict(r) for r in rows]
 def events(self,i):
  with sqlite3.connect(self.path) as c:
   c.row_factory=sqlite3.Row;return [dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY id',(i,)).fetchall()]
