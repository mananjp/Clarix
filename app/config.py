import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base Directory of the application
BASE_DIR = Path(__file__).resolve().parent.parent

# Application environment. Options: development | staging | production (default).
# An unset/blank ENVIRONMENT is treated as "production" so that demo user
# seeding and other dev-only behaviour never run by accident on a deployed host.
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()

# Database configuration
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Upload directory
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --- Database selection -----------------------------------------------------
#   USE_POSTGRES=true  -> connect to the local Docker PostgreSQL (see docker-compose.yml)
#   NEON_URL           -> (legacy) managed Neon PostgreSQL
#   DATABASE_URL       -> explicit connection string (highest priority after USE_POSTGRES)
#   default            -> local SQLite at data/sfdr.db
#
# Precedence:
#   1. USE_POSTGRES=true  -> local Docker Postgres
#   2. NEON_URL           -> managed Postgres
#   3. DATABASE_URL       -> explicit override
#   4. SQLite fallback
def _build_database_url() -> str:
    if os.getenv("USE_POSTGRES", "").strip().lower() in ("1", "true", "yes"):
        user = os.getenv("POSTGRES_USER", "clarix")
        password = os.getenv("POSTGRES_PASSWORD", "clarix")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "55432")
        db = os.getenv("POSTGRES_DB", "clarix")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    if os.getenv("NEON_URL"):
        return os.getenv("NEON_URL")
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    return f"sqlite:///{DATA_DIR}/sfdr.db"


DATABASE_URL = _build_database_url()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# JWT signing secret - fail fast with a clearly actionable error if unset
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))" '
        "and add it to your .env file."
    )

# Default settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-oss-120b")
SUPPORTED_MODELS = ["openai/gpt-oss-120b", "gemma2-9b-it"]

# ---------------------------------------------------------------------------
# EU data residency & hosting configuration
# ---------------------------------------------------------------------------
#   DATA_RESIDENCY_REGION   -> EU region where regulatory data is hosted
#                             (e.g. "eu-central-1", "eu-west-1", "eu")
#   DATA_RESIDENCY_VENDOR   -> cloud/hosting vendor (aws | azure | gcp | self)
#   DATA_RESIDENCY_STATEMENT-> short human description surfaced in ops
DATA_RESIDENCY_REGION = os.getenv("DATA_RESIDENCY_REGION", "eu-central-1")
DATA_RESIDENCY_VENDOR = os.getenv("DATA_RESIDENCY_VENDOR", "aws")
DATA_RESIDENCY_STATEMENT = os.getenv(
    "DATA_RESIDENCY_STATEMENT",
    "Regulatory disclosure data is hosted within the European Union.",
)
