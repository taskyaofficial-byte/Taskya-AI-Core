import sqlite3, json
from datetime import datetime,timezone

class MemoryStore:
    def __init__(self,path):
        self.path=str(path)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_message TEXT,status TEXT,result TEXT,created_at TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)")
    def now(self): return datetime.now(timezone.utc).isoformat()
    def task(self,i,m):
        with sqlite3.connect(self.path) as c:c.execute("INSERT INTO tasks VALUES(?,?,?,?,?)",(i,m,"running",None,self.now()))
    def finish(self,i,s,r):
        with sqlite3.connect(self.path) as c:c.execute("UPDATE tasks SET status=?,result=? WHERE id=?",(s,r,i))
    def event(self,i,t,p):
        with sqlite3.connect(self.path) as c:c.execute("INSERT INTO events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)",(i,t,json.dumps(p,ensure_ascii=False,default=str),self.now()))
