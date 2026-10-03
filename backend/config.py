import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
DATABASE_URL = os.getenv("DATABASE_URL") or ("sqlite:////tmp/crossmind.db" if os.getenv("VERCEL") else "sqlite:///./crossmind.db")
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
CORS = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "4")) * 1024 * 1024
EXTS = {".pdf", ".pptx", ".docx", ".xlsx", ".xls", ".csv", ".txt"}
