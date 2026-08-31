import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import BASE_DIR
from app.database import Base, engine

from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.projects import router as projects_router
from app.routers.documents import router as documents_router
from app.routers.answers import router as answers_router
from app.routers.regulation_fields import router as regulation_fields_router
from app.routers.what_if import router as what_if_router
from app.routers.export import router as export_router
from app.routers.audit import router as audit_router
from app.routers.analytics import router as analytics_router
from app.routers.settings import router as settings_router
from app.routers.data_retention import router as data_retention_router

# Initialize database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Regulatory Intelligence & Compliance Workflow Engine API",
    description="GenAI-powered compliance workspace with legal consequence mapping across SFDR, CSRD, and multi-framework regulatory obligations.",
    version="2.0.0"
)

@app.on_event("startup")
def on_startup():
    from app.seed_regulations import seed_database
    from app.auth import SECRET_KEY

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is not set. Set the SECRET_KEY environment variable before starting the server."
        )

    try:
        seed_database()
        logging.info("Database successfully verified/seeded on startup.")
    except Exception as e:
        logging.error("Error seeding database on startup: %s", e)

# Global Resilience Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.error("Unhandled exception: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}}
    )

# CORS middleware config
allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include sub-routers (routes split out of the monolith)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(answers_router)
app.include_router(regulation_fields_router)
app.include_router(what_if_router)
app.include_router(export_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(data_retention_router)

# Serve CSS, JS, and Assets
static_dir = os.path.join(BASE_DIR, "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Ensure assets are served at /assets for the build links in index.html
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Catch-all: serve the frontend SPA for ALL non-API, non-static routes
# This enables React Router client-side navigation to work on page reload
@app.get("/{path:path}", response_class=HTMLResponse)
def serve_index(path: str = ""):
    index_path = os.path.join(BASE_DIR, "app", "static", "index.html")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), headers=headers)
    return HTMLResponse(content="""
    <html>
        <head><title>Clarix | Regulatory Intelligence Engine</title></head>
        <body style="font-family:sans-serif; text-align:center; padding-top:100px;">
            <h1>Regulatory Intelligence &amp; Compliance Workflow Engine</h1>
            <p>Please build/create the static folder and index.html file to view the rich UI workspace.</p>
            <p><a href="/docs">View REST API Documentation (Swagger)</a></p>
        </body>
    </html>
    """, headers=headers)
