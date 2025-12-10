import os
import logging
import threading
import time
from contextlib import contextmanager
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request, Response
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ============================================================
# 1️⃣ Load environment (.env)
# ============================================================
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
    print(f"✅ .env loaded from: {env_path}")
else:
    print("⚠️  .env file not found.")

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
        pool_size=10,                # Persistent connections
        max_overflow=20,             # Burst capacity
        pool_timeout=60,             # Wait 60s if pool is full
        pool_recycle=1200,           # Recycle every 20min (avoid stale TCP)
        connect_args={"connect_timeout": 30},  # Timeout for new connection
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
        logging.error(f"⚠️ Rolled back transaction due to: {e}")
        raise
    finally:
        db.close()

# ============================================================
# 5️⃣ Dependency for FastAPI routes
# ============================================================
def get_db(db_key: str = "DB_MAIN"):
    """
    Provides a SQLAlchemy session to FastAPI routes.
    Ensures rollback + close on exit.
    """
    SessionLocal = SessionFactories.get(db_key)
    if not SessionLocal:
        raise ValueError(f"Database '{db_key}' not configured")

    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logging.error(f"⚠️ Rollback triggered in get_db(): {e}")
        raise
    finally:
        db.close()

# ============================================================
# 6️⃣ Optional Middleware for global cleanup
# ============================================================
def register_db_middleware(app: FastAPI):
    """
    Ensures SQLAlchemy sessions and engines are cleaned up
    after each HTTP request (safety net).
    """
    @app.middleware("http")
    async def db_session_cleanup(request: Request, call_next):
        response = Response("Internal server error", status_code=500)
        try:
            response = await call_next(request)
        finally:
            for key, engine in engines.items():
                try:
                    engine.dispose()  # clean pooled connections
                except Exception as e:
                    logging.warning(f"⚠️ Engine dispose failed for {key}: {e}")
        return response

# ============================================================
# 7️⃣ Background watchdog to dispose stale connections
# ============================================================
def connection_watchdog(interval: int = 3600):
    """
    Runs in background to dispose pooled connections every hour.
    Prevents leaked 'idle' connections filling slots.
    """
    while True:
        time.sleep(interval)
        for key, engine in engines.items():
            try:
                engine.dispose()
                logging.info(f"♻️  Disposed stale connections for {key}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to dispose connections for {key}: {e}")

# Start watchdog thread
threading.Thread(target=connection_watchdog, daemon=True).start()

# ============================================================
# 8️⃣ Self-test utility
# ============================================================
if __name__ == "__main__":
    print("🧪 Testing database connection...")
    if "DB_MAIN" in engines:
        try:
            with engines["DB_MAIN"].connect() as conn:
                db_name, schema = conn.execute(
                    text("SELECT current_database(), current_schema();")
                ).fetchone()
                active_conn = conn.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database();")
                ).scalar()
                print(f"✅ Connected to DB: {db_name}, schema: {schema}")
                print(f"🔢 Active connections: {active_conn}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
    else:
        print("❌ DB_MAIN not configured")
