from fastapi import FastAPI
from .api import router

app=FastAPI(title='Taskya AI', version='1.5.0')
app.include_router(router, prefix='/api')
@app.get('/health')
def health(): return {'ok':True,'version':'1.5.0'}
