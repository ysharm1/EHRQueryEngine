from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.api.routes import router
from app.api.extraction_routes import router as extraction_router
from app.api.clinical_routes import router as clinical_router
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
app.include_router(extraction_router, prefix="/api")
app.include_router(clinical_router, prefix="/api")


# Global exception handler to ensure CORS headers are set on all errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    import logging
    logger = logging.getLogger(__name__)
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.url.path}: {tb}")

    origin = request.headers.get("origin", "*")
    allowed = settings.cors_origins_list
    cors_origin = origin if (allowed == ["*"] or origin in allowed) else "null"

    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Server error: {str(exc)}",
            "traceback": tb[-1000:],
        },
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Research Dataset Builder API",
        "version": "1.1.0-upload-fix",
        "docs": "/docs"
    }
