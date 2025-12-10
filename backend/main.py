from fastapi import FastAPI
from .database import Base, engines
from .routers import drivingdistance_routes

# Initialize FastAPI app
app = FastAPI(
    title="🚀 Analytics Backend API",
    description="Backend service for multi-database analytics and data pipelines.",
    version="1.1.1"
)

# Auto-create tables across all connected databases
for key, engine in engines.items():
    Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(drivingdistance_routes.router)

# Root endpoint
@app.get("/")
def root():
    return {
        "status": "✅ OK",
        "service": "Analytics Backend",
        "message": "📊 Multi-DB Analytics API is running!"
    }
