import json, time
from pathlib import Path

class BenchmarkRunner:
    def run(self, agent, cases_path):
        cases=json.loads(Path(cases_path).read_text(encoding='utf-8'))
        results=[]
        for c in cases:
            started=time.time(); r=agent.run(c['prompt'], c.get('language','auto')); elapsed=time.time()-started
            results.append({'id':c.get('id'), 'status':r.get('status'), 'elapsed_s':round(elapsed,3), 'answer':r.get('answer','')})
        return {'count':len(results),'results':results}
