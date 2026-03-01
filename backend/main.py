"""FastAPI application entry point."""
import logging
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.telemetry.config import configure_telemetry
from backend.audit.audit_logger import get_audit_logger
from backend.api import upload, ocr, analyze, wizard, stream, audit, traces, forms

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()

    # Export API keys to os.environ so SDKs that read env vars directly
    # (e.g. OpenAI Agents SDK) can find them.
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)

    # Initialize telemetry
    configure_telemetry(settings)
    logger.info("OpenTelemetry configured")

    # Start audit logger background writer
    audit_logger = get_audit_logger()
    audit_logger.start()
    logger.info("Audit logger started")

    logger.info(f"Tax AI Backend starting — model: {settings.anthropic_advance_llm_model}")

    yield

    # Shutdown
    await audit_logger.stop()
    logger.info("Tax AI Backend shutting down")


app = FastAPI(
    title="Tax AI Backend",
    version="1.0.0",
    description="AI-powered tax assistant with dual-LLM analysis",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(ocr.router, prefix="/api", tags=["ocr"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(wizard.router, prefix="/api", tags=["wizard"])
app.include_router(stream.router, prefix="/api", tags=["stream"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
app.include_router(traces.router, prefix="/api", tags=["traces"])
app.include_router(forms.router, prefix="/api", tags=["forms"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
