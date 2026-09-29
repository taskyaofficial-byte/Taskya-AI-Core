from fastapi import FastAPI, Request
from .api import router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title='Taskya AI', version='1.5.0')
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router, prefix='/api')

@app.get('/health')
@limiter.limit("30/minute")
def health(request: Request):
    return {'ok': True, 'version': '1.5.0'}
