from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router
from app.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

# Run one-time startup tasks (password migration + sample data)
try:
    from app.init_db import migrate_passwords, init_database, create_sample_data
    init_database()
    create_sample_data()
    migrate_passwords()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Startup init warning: {e}")
    pass  # Never block startup

app = FastAPI(
    title="Research Dataset Builder API",
    description="Platform for generating structured datasets from biomedical data sources",
    version="1.0.0"
)

# CORS middleware — origins controlled via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_origins_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Research Dataset Builder API",
        "version": "1.0.0",
        "docs": "/docs"
    }
