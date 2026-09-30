import subprocess,tempfile,os
from ..config import DOCKER_ENABLED,DOCKER_IMAGE,DOCKER_TIMEOUT
def run_python(code,timeout=None):
 if not DOCKER_ENABLED:return {'error':'Docker execution is disabled'}
 if len(code)>100000:return {'error':'Code too large'}
 timeout=timeout or DOCKER_TIMEOUT
 with tempfile.TemporaryDirectory(prefix='taskya_') as d:
  open(os.path.join(d,'main.py'),'w',encoding='utf-8').write(code)
  cmd=['docker','run','--rm','--network','none','--cpus','1','--memory','512m','--pids-limit','128','-v',f'{d}:/work:rw','-w','/work',DOCKER_IMAGE,'python','main.py']
  try:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout);return {'returncode':p.returncode,'stdout':p.stdout[-12000:],'stderr':p.stderr[-12000:]}
  except subprocess.TimeoutExpired:return {'error':f'timed out after {timeout}s'}
  except FileNotFoundError:return {'error':'Docker CLI not found'}
