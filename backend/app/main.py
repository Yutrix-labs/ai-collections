"""
FastAPI main application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.utils.redis_client import redis_client
from app.api import rest, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Startup: Connect to Redis
    Shutdown: Disconnect from Redis
    """
    # Startup
    print("Starting up AI Collections Assistant API...")
    await redis_client.connect()
    print("Connected to Redis")

    yield

    # Shutdown
    print("Shutting down...")
    await redis_client.disconnect()
    print("Disconnected from Redis")


# Create FastAPI app
app = FastAPI(
    title="AI Collections Assistant API",
    description="Real-time AI-powered insights for collections call agents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development/testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rest.router, prefix="/api/v1", tags=["REST"])
app.include_router(websocket.router, prefix="/api/v1", tags=["WebSocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AI Collections Assistant API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
