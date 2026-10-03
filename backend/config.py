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
    return u

DATABASE_URL = _clean_db_url(os.getenv("DATABASE_URL")) or ("sqlite:////tmp/crossmind.db" if os.getenv("VERCEL") else "sqlite:///./crossmind.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
CORS = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "4")) * 1024 * 1024
EXTS = {".pdf", ".pptx", ".docx", ".xlsx", ".xls", ".csv", ".txt"}
