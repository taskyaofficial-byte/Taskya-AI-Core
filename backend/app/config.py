import os
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[2]
load_dotenv(BASE / ".env")
load_dotenv(BASE / "backend" / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
# Current default; override with any Groq model available to your account.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
MAX_STEPS = int(os.getenv("TASKYA_AI_MAX_STEPS", "8"))
WORKSPACE = (BASE / os.getenv("TASKYA_AI_WORKSPACE", "workspace")).resolve()
ARTIFACTS = (BASE / os.getenv("TASKYA_AI_ARTIFACTS", "artifacts")).resolve()
DB_PATH = (BASE / os.getenv("TASKYA_AI_DB", "taskyaai.sqlite3")).resolve()

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing. Copy .env.example to .env and add your key.")
WORKSPACE.mkdir(parents=True, exist_ok=True)
ARTIFACTS.mkdir(parents=True, exist_ok=True)
