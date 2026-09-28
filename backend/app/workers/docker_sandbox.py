import subprocess, tempfile, os, textwrap

class DockerSandbox:
    def run_python(self, code, timeout=20, memory='256m'):
        if not code.strip(): raise ValueError('code is empty')
        with tempfile.TemporaryDirectory() as d:
            src=os.path.join(d,'main.py'); open(src,'w',encoding='utf-8').write(code)
            cmd=['docker','run','--rm','--network','none','--cpus','1','--memory',memory,'--pids-limit','64','-v',f'{d}:/work:ro','taskya-python-sandbox','python','/work/main.py']
            try: p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
            except FileNotFoundError as e: raise RuntimeError('Docker is not installed or not on PATH') from e
            except subprocess.TimeoutExpired: return {'ok':False,'error':'sandbox timeout'}
            return {'ok':p.returncode==0,'stdout':p.stdout[-20000:],'stderr':p.stderr[-10000:],'returncode':p.returncode}
