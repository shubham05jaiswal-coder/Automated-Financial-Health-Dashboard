import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://finance_app:change_me_local_only@localhost:5432/finance_dashboard",
)
INPUT_DIR = (PROJECT_ROOT / os.getenv("INPUT_DIR", "data/input")).resolve()
LOG_DIR = (PROJECT_ROOT / os.getenv("LOG_DIR", "logs")).resolve()
MAX_REJECTED_ROWS = int(os.getenv("MAX_REJECTED_ROWS", "100"))

LOG_DIR.mkdir(parents=True, exist_ok=True)
