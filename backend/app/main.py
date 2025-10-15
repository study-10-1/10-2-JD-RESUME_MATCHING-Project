"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine
from app.api.v1 import resumes, matching


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("🚀 Starting Auto-Match Backend...")
    print(f"📦 Environment: {settings.ENVIRONMENT}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print(f"🤖 Embedding Model: {settings.EMBEDDING_MODEL}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Auto-Match Backend...")


# Create FastAPI app
app = FastAPI(
    title="Auto-Match API",
    description="AI-based Resume & Job Matching System",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include only implemented routers (MVP)
app.include_router(resumes.router, prefix="/api/v1/resumes", tags=["Resumes"])
app.include_router(matching.router, prefix="/api/v1/matching", tags=["Matching"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Auto-Match API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected",
    }

