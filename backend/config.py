import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
def _clean_db_url(raw):
    """Tolerate the usual copy/paste mistakes and always use the psycopg2 driver
    (SQLAlchemy 2.1+ would otherwise default to 'psycopg', which is not installed)."""
    u = (raw or "").strip()
    if u.lower().startswith("psql "):          # Neon shows:  psql 'postgresql://...'
        u = u[5:].strip()
    u = u.strip("'\"` ")                        # stray quotes
    for prefix in ("postgres://", "postgresql://"):
        if u.startswith(prefix):
            u = "postgresql+psycopg2://" + u[len(prefix):]
    if u.startswith("postgresql+psycopg2://") and "?" in u:
        base, query = u.split("?", 1)
        keep = [q for q in query.split("&") if q and not q.startswith("channel_binding")]
        u = base + ("?" + "&".join(keep) if keep else "")
    if u.startswith("postgresql+psycopg2://") and "sslmode=" not in u and "localhost" not in u and "127.0.0.1" not in u:
        u += ("&" if "?" in u else "?") + "sslmode=require"      # never talk to a hosted database unencrypted
    return u

DATABASE_URL = _clean_db_url(os.getenv("DATABASE_URL")) or ("sqlite:////tmp/crossmind.db" if os.getenv("VERCEL") else "sqlite:///./crossmind.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
CORS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if o.strip() and o.strip() != "*"]
PROD = bool(os.getenv("VERCEL") or os.getenv("RENDER") or os.getenv("ENV") == "production")
RATE_LIMIT_ON = os.getenv("RATE_LIMIT", "on").lower() != "off"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
if os.getenv("VERCEL"):                           # Vercel rejects request bodies above ~4.5 MB, whatever we allow
    MAX_UPLOAD_MB = min(MAX_UPLOAD_MB, 4)
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024          # per request (all files together)
SESSION_HOURS = min(float(os.getenv("SESSION_HOURS", "3")), 12.0)   # login lasts this long, then the user is signed out
EXTS = {".pdf", ".pptx", ".docx", ".xlsx", ".xls", ".csv", ".txt"}

SECRET_OK = len(SECRET_KEY) >= 16 and not SECRET_KEY.lower().startswith(("dev-secret", "change-this", "changeme", "your-secret", "generate"))
MAX_TEXT_CHARS = 5_000_000
