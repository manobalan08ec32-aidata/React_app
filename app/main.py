"""
FastAPI application for Healthcare Finance Analytics API.
Provides WebSocket chat endpoint and REST session management.
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from app.storage.databricks import DatabricksStorage

# Global storage instance
storage: DatabricksStorage = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    global storage

    # Startup
    print("Starting Healthcare API...")
    storage = DatabricksStorage()

    # Initialize storage tables (creates if not exists)
    try:
        await storage.initialize()
        print("Storage initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize storage: {e}")
        print("Storage will be initialized on first use")

    yield

    # Shutdown
    print("Shutting down Healthcare API...")
    if storage:
        await storage.close()


# Create FastAPI app
app = FastAPI(
    title="Healthcare Finance Analytics API",
    description="WebSocket-based chat API with streaming responses for healthcare finance analysis",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================================
# HEALTH ENDPOINTS
# =========================================================================

@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "service": "Healthcare Finance Analytics API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.
    Verifies API is running and storage is connected.
    """
    storage_healthy = False

    if storage:
        try:
            storage_healthy = await storage.health_check()
        except Exception:
            storage_healthy = False

    return {
        "status": "healthy" if storage_healthy else "degraded",
        "api": "running",
        "storage": "connected" if storage_healthy else "disconnected"
    }


@app.get("/health/live")
async def health_live():
    """Kubernetes liveness probe - is the app running?"""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """Kubernetes readiness probe - is the app ready to serve traffic?"""
    if storage:
        try:
            healthy = await storage.health_check()
            if healthy:
                return {"status": "ready"}
        except Exception:
            pass

    return {"status": "not_ready"}, 503


# =========================================================================
# IMPORT ROUTERS
# =========================================================================

from app.routers import chat, sessions
app.include_router(chat.router, prefix="/ws", tags=["chat"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


def get_storage() -> DatabricksStorage:
    """Dependency injection for storage."""
    return storage


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
