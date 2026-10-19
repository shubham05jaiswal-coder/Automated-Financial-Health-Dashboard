from sqlalchemy import create_engine, text
from src.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)

def check_connection():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
