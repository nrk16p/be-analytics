from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# ✅ Load .env from the parent folder (analytics/.env)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
print(f"✅ Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)

if not os.path.exists(env_path):
    print(f"⚠️  .env file not found at: {env_path}")
else:
    print(f"✅ Loading .env from: {env_path}")

load_dotenv(dotenv_path=env_path)

# ============================================================
# ✅ 2️⃣ Read database URLs
# ============================================================
DB_URLS = {
    "DB_MAIN": os.getenv("DB_MAIN"),
    "DB_ANALYTICS": os.getenv("DB_ANALYTICS")
}

print("🔗 Database URLs loaded:")
for key, val in DB_URLS.items():
    if val:
        print(f"  {key} → {val.split('@')[-1]}")  # show only host/db
    else:
        print(f"  ⚠️ {key} missing in .env")

# ============================================================
# ✅ 3️⃣ Create SQLAlchemy engines and session factories
# ============================================================
engines = {}
SessionFactories = {}

for key, url in DB_URLS.items():
    if url:
        engine = create_engine(
            url,
            pool_pre_ping=True,   # auto-reconnect dead connections
            pool_size=10,         # maintain up to 10 persistent connections
            max_overflow=20,      # allow 20 temporary bursts
            echo=False            # set True for SQL debug logs
        )
        engines[key] = engine
        SessionFactories[key] = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )

# Base class for all ORM models
Base = declarative_base()

# ============================================================
# ✅ 4️⃣ Database dependency for FastAPI routes
# ============================================================
def get_db(db_key: str = "DB_MAIN"):
    """
    Dependency that provides a SQLAlchemy session.
    Default connects to DB_MAIN unless otherwise specified.
    """
    SessionLocal = SessionFactories.get(db_key)
    if not SessionLocal:
        raise ValueError(f"Database '{db_key}' is not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# ✅ 5️⃣ (Optional) Quick self-test
# ============================================================
if __name__ == "__main__":
    from sqlalchemy import text
    if "DB_MAIN" in engines:
        with engines["DB_MAIN"].connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_schema();")).fetchone()
            print(f"✅ Connected to database '{result[0]}' schema '{result[1]}'")
    else:
        print("❌ No DB_MAIN engine initialized.")
