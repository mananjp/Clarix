"""
Clarix — Regulatory Intelligence & Compliance Workflow Engine

FastAPI application entrypoint:
  - Structured logging & request correlation ID
  - Sentry APM integration (optional via SENTRY_DSN)
  - Rate limiting via SlowAPI
  - Global exception handling & CORS
  - Modular router composition
  - Static file serving & SPA catch-all
"""

import os
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import BASE_DIR
from app.database import Base, engine
from app.logging_config import setup_logging, request_id_ctx
from app.limiter import limiter

# ---------------------------------------------------------------------------
# Initialise Logging
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise Sentry (Graceful if SENTRY_DSN configured)
# ---------------------------------------------------------------------------
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[FastApiIntegration()],
        )
        logger.info("Sentry APM initialized successfully.")
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)

# ---------------------------------------------------------------------------
# Initialise database tables
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Regulatory Intelligence & Compliance Workflow Engine API",
    description=(
        "GenAI-powered compliance workspace with legal consequence mapping "
        "across SFDR, CSRD, and multi-framework regulatory obligations."
    ),
    version="2.0.0",
)
app.state.limiter = limiter


# ---------------------------------------------------------------------------
# Middleware: Request Correlation ID
# ---------------------------------------------------------------------------
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("Rate limit exceeded on path %s for IP %s", request.url.path, request.client.host if request.client else "unknown")
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    if SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            }
        },
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    from app.seed_regulations import seed_database
    from app.auth import SECRET_KEY

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is not set. Set the SECRET_KEY environment "
            "variable before starting the server."
        )

    try:
        seed_database()
        logger.info("Database successfully verified/seeded on startup.")
    except Exception as e:
        logger.error("Error seeding database on startup: %s", e)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
allowed_origins = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.projects import router as projects_router
from app.routers.documents import router as documents_router
from app.routers.answers import router as answers_router
from app.routers.what_if import router as what_if_router
from app.routers.export import router as export_router
from app.routers.audit import router as audit_router
from app.routers.analytics import router as analytics_router
from app.routers.settings import router as settings_router
from app.routers.regulation_fields import router as regulation_fields_router
from app.routers.data_retention import router as retention_router
from app.routers.greenwashing import router as greenwashing_router
from app.routers.cross_framework import router as cross_framework_router
from app.routers.merkle_audit import router as merkle_audit_router
from app.routers.intake import router as intake_router
from app.routers.enterprise_sso import router as enterprise_sso_router
from app.routers.matrix import router as matrix_router
from app.routers.auditor import router as auditor_router
from app.routers.esg_data_feed import router as esg_feed_router
from app.routers.regulatory_content import router as regulatory_content_router
from app.routers.double_materiality import router as double_materiality_router
from app.routers.ghg import router as ghg_router
from app.routers.benchmarking import router as benchmarking_router
from app.routers.invites import router as invites_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(answers_router)
app.include_router(what_if_router)
app.include_router(export_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(regulation_fields_router)
app.include_router(retention_router)
app.include_router(greenwashing_router)
app.include_router(cross_framework_router)
app.include_router(merkle_audit_router)
app.include_router(intake_router)
app.include_router(enterprise_sso_router)
app.include_router(matrix_router)
app.include_router(auditor_router)
app.include_router(esg_feed_router)
app.include_router(regulatory_content_router)
app.include_router(double_materiality_router)
app.include_router(ghg_router)
app.include_router(benchmarking_router)
app.include_router(invites_router)


# ---------------------------------------------------------------------------
# Static file serving & SPA catch-all
# ---------------------------------------------------------------------------
static_dir = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", response_class=HTMLResponse)
def serve_index(path: str = ""):
    index_path = os.path.join(BASE_DIR, "app", "static", "index.html")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), headers=headers)
    return HTMLResponse(
        content="""
    <html>
        <head><title>Clarix | Regulatory Intelligence Engine</title></head>
        <body style="font-family:sans-serif; text-align:center; padding-top:100px;">
            <h1>Regulatory Intelligence &amp; Compliance Workflow Engine</h1>
            <p>Please build/create the static folder and index.html file to view the rich UI workspace.</p>
            <p><a href="/docs">View REST API Documentation (Swagger)</a></p>
        </body>
    </html>
    """,
        headers=headers,
    )
