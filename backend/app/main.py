from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
app=FastAPI(title='Taskya AI',version='1.5.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
@app.get('/')
def health():return {'name':'Taskya AI','status':'online','version':'1.5.0','mode':'plan-act-observe-verify'}
app.include_router(router,prefix='/api')
