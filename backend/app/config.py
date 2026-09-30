import os
from pathlib import Path
from dotenv import load_dotenv
BASE=Path(__file__).resolve().parents[2]
load_dotenv(BASE/'.env'); load_dotenv(BASE/'backend/.env')
GROQ_API_KEY=os.getenv('GROQ_API_KEY','').strip()
TAVILY_API_KEY=os.getenv('TAVILY_API_KEY','').strip()
GROQ_MODEL=os.getenv('GROQ_MODEL','openai/gpt-oss-120b').strip()
MAX_STEPS=int(os.getenv('TASKYA_AI_MAX_STEPS','10'))
WORKSPACE=(BASE/os.getenv('TASKYA_AI_WORKSPACE','workspace')).resolve()
ARTIFACTS=(BASE/os.getenv('TASKYA_AI_ARTIFACTS','artifacts')).resolve()
UPLOADS=(BASE/os.getenv('TASKYA_AI_UPLOADS','uploads')).resolve()
DB_PATH=(BASE/os.getenv('TASKYA_AI_DB','taskyaai.sqlite3')).resolve()
BROWSER_HEADLESS=os.getenv('TASKYA_BROWSER_HEADLESS','true').lower()=='true'
ALLOWED_DOMAINS=[x.strip().lower() for x in os.getenv('TASKYA_BROWSER_ALLOWED_DOMAINS','*').split(',') if x.strip()]
DOCKER_ENABLED=os.getenv('TASKYA_DOCKER_ENABLED','true').lower()=='true'
DOCKER_IMAGE=os.getenv('TASKYA_DOCKER_IMAGE','python:3.11-slim')
DOCKER_TIMEOUT=int(os.getenv('TASKYA_DOCKER_TIMEOUT','30'))
AUTH_SECRET=os.getenv('TASKYA_AUTH_SECRET','change-me')
ADMIN_EMAIL=os.getenv('TASKYA_ADMIN_EMAIL','admin@taskya.local')
ADMIN_PASSWORD=os.getenv('TASKYA_ADMIN_PASSWORD','change-me')
PLAN_PRICE_INR=int(os.getenv('TASKYA_PLAN_PRICE_INR','19'))
for p in (WORKSPACE,ARTIFACTS,UPLOADS): p.mkdir(parents=True,exist_ok=True)
