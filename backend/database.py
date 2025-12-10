from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
import logging

# ============================================================
# 1️⃣ Load .env (parent directory)
# ============================================================
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    print(f"✅ .env loaded from: {env_path}")
else:
    print(f"⚠️  .env file not found at: {env_path}")

# ============================================================
# 2️⃣ Database URLs
# ============================================================
DB_URLS = {
    "DB_MAIN": os.getenv("DB_MAIN"),
    "DB_ANALYTICS": os.getenv("DB_ANALYTICS"),
}

print("🔗 Database URLs:")
for key, val in DB_URLS.items():
    if val:
        print(f"  {key} → {val.split('@')[-1]}")
    else:
        print(f"  ⚠️ {key} missing in .env")

# ============================================================
# 3️⃣ Create engines and session factories
# ============================================================
engines = {}
SessionFactories = {}

for key, url in DB_URLS.items():
    if not url:
        continue

    engine = create_engine(
        url,
        echo=False,                  # Debug SQL if needed
        pool_pre_ping=True,          # Detect dropped connections
        pool_size=5,                # Persistent connections
        max_overflow=20,             # Burst capacity
        pool_timeout=60,             # Wait 60s if pool is full
        pool_recycle=1800,           # Recycle every 30min
        connect_args={"connect_timeout": 30},  # Timeout to establish conn
    )

    engines[key] = engine
    SessionFactories[key] = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

Base = declarative_base()

# ============================================================
# 4️⃣ Safe context manager for standalone scripts
# ============================================================
@contextmanager
def get_db_session(db_key: str = "DB_MAIN"):
    """
    Context manager for manual DB access outside FastAPI routes.
    Example:
        with get_db_session() as db:
            db.execute(...)
    """
    SessionLocal = SessionFactories.get(db_key)
    if not SessionLocal:
        raise ValueError(f"Database '{db_key}' not configured")

    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️  Rolled back transaction due to: {e}")
        raise
    finally:
        db.close()

# ============================================================
# 5️⃣ Dependency for FastAPI routes
# ============================================================
def get_db(db_key: str = "DB_MAIN"):
    """
    Provides a SQLAlchemy session to FastAPI routes.
    Ensures close/rollback on exit.
    """
    SessionLocal = SessionFactories.get(db_key)
    if not SessionLocal:
        raise ValueError(f"Database '{db_key}' not configured")

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ============================================================
# 6️⃣ Optional: Auto-close safeguard middleware for FastAPI
# ============================================================
def register_db_middleware(app: FastAPI):
    """
    Ensures all SQLAlchemy sessions are cleaned up
    even if an unhandled exception occurs.
    """
    @app.middleware("http")
    async def db_session_cleanup(request: Request, call_next):
        response = Response("Internal server error", status_code=500)
        try:
            response = await call_next(request)
        finally:
            for key, factory in SessionFactories.items():
                try:
                    factory().close_all()
                except Exception as e:
                    logging.warning(f"⚠️ Failed to close sessions for {key}: {e}")
        return response

# ============================================================
# 7️⃣ Self-test utility
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing database connection...")
    if "DB_MAIN" in engines:
        try:
            with engines["DB_MAIN"].connect() as conn:
                result = conn.execute(text("SELECT current_database(), current_schema();")).fetchone()
                print(f"✅ Connected to DB: {result[0]}, schema: {result[1]}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
    else:
        print("❌ DB_MAIN not configured")
