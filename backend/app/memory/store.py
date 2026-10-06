import json
import sqlite3
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_message TEXT,status TEXT,result TEXT,created_at TEXT,updated_at TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)')
            c.execute('''CREATE TABLE IF NOT EXISTS task_meta(
                task_id TEXT PRIMARY KEY,
                plan TEXT,
                language TEXT,
                web_enabled INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS task_metrics(
                task_id TEXT PRIMARY KEY,
                steps INTEGER DEFAULT 0,
                tool_calls INTEGER DEFAULT 0,
                successful_tools INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                recoveries INTEGER DEFAULT 0,
                sources INTEGER DEFAULT 0,
                artifacts INTEGER DEFAULT 0,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL DEFAULT 0
            )''')

    def now(self):
        return datetime.now(timezone.utc).isoformat()

    def task(self, i, m, status='queued'):
        n = self.now()
        with sqlite3.connect(self.path) as c:
            c.execute('''INSERT INTO tasks(id,user_message,status,result,created_at,updated_at)
                         VALUES(?,?,?,?,?,?)
                         ON CONFLICT(id) DO UPDATE SET user_message=excluded.user_message,status=excluded.status,updated_at=excluded.updated_at''',
                      (i, m, status, None, n, n))

    def set_status(self, i, s, r=None):
        with sqlite3.connect(self.path) as c:
            c.execute('UPDATE tasks SET status=?,result=COALESCE(?,result),updated_at=? WHERE id=?',
                      (s, r, self.now(), i))

    def event(self, i, t, p):
        with sqlite3.connect(self.path) as c:
            c.execute('INSERT INTO events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)',
                      (i, t, json.dumps(p, ensure_ascii=False, default=str), self.now()))

    def ensure_meta(self, task_id, plan=None, language='auto', web_enabled=False):
        n = self.now()
        with sqlite3.connect(self.path) as c:
            c.execute('''INSERT INTO task_meta(task_id,plan,language,web_enabled,created_at,updated_at)
                         VALUES(?,?,?,?,?,?)
                         ON CONFLICT(task_id) DO UPDATE SET
                         plan=COALESCE(excluded.plan,task_meta.plan),
                         language=excluded.language,web_enabled=excluded.web_enabled,updated_at=excluded.updated_at''',
                      (task_id, json.dumps(plan, ensure_ascii=False) if plan is not None else None,
                       language, 1 if web_enabled else 0, n, n))

    def update_plan(self, task_id, plan):
        self.ensure_meta(task_id, plan=plan)

    def init_metrics(self, task_id):
        with sqlite3.connect(self.path) as c:
            c.execute('''INSERT OR IGNORE INTO task_metrics(task_id,started_at) VALUES(?,?)''', (task_id, self.now()))

    def metric_inc(self, task_id, field, amount=1):
        allowed = {'steps','tool_calls','successful_tools','errors','recoveries','sources','artifacts'}
        if field not in allowed:
            raise ValueError('Unsupported metric: ' + field)
        self.init_metrics(task_id)
        with sqlite3.connect(self.path) as c:
            c.execute(f'UPDATE task_metrics SET {field}=COALESCE({field},0)+? WHERE task_id=?', (amount, task_id))

    def finish_metrics(self, task_id):
        self.init_metrics(task_id)
        finished = self.now()
        with sqlite3.connect(self.path) as c:
            row = c.execute('SELECT started_at FROM task_metrics WHERE task_id=?', (task_id,)).fetchone()
            duration = 0.0
            if row and row[0]:
                try:
                    start = datetime.fromisoformat(row[0])
                    end = datetime.fromisoformat(finished)
                    duration = max(0.0, (end - start).total_seconds())
                except Exception:
                    duration = 0.0
            c.execute('UPDATE task_metrics SET finished_at=?,duration_seconds=? WHERE task_id=?',
                      (finished, duration, task_id))
        return duration

    def metrics(self, task_id):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute('SELECT * FROM task_metrics WHERE task_id=?', (task_id,)).fetchone()
            return dict(row) if row else None

    def get_task(self, i):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            r = c.execute('SELECT * FROM tasks WHERE id=?', (i,)).fetchone()
            return dict(r) if r else None

    def events(self, i):
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY id', (i,)).fetchall()]
