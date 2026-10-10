import os, io, csv, json, html, time, datetime as dt, collections, random, string
import jwt, bcrypt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import re
from urllib.parse import parse_qsl, urlencode
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

import config, parser, nlp, crossword, quiz_generator
import topic as topic_mod
from models import *

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "data", "sample_data")

app = FastAPI(title="CrossMind", docs_url=None, redoc_url=None, openapi_url=None)   # no public API docs
app.add_middleware(CORSMiddleware, allow_origins=config.CORS, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "Authorization", "X-Requested-With"])


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
def clean(v, tags=True):
    """Trim, drop control characters and (for short fields) angle brackets so markup can never be stored."""
    v = _CTRL.sub("", v).strip()
    return re.sub(r"[<>]", "", v) if tags else v

from pydantic import model_validator
class Clean(BaseModel):
    """Base for request bodies: sanitises every short text field. Passwords and long notes are left untouched."""
    @model_validator(mode="before")
    @classmethod
    def _sanitise(cls, data):
        if isinstance(data, dict):
            return {k: (v if k in ("password", "text") or not isinstance(v, str) else clean(v)) for k, v in data.items()}
        return data

def check_pw(p):
    if len(p) < 8 or not re.search(r"[A-Za-z]", p) or not re.search(r"\d", p):
        raise HTTPException(422, "Password must be at least 8 characters and include a letter and a number.")
    if len(p.encode()) > 72:
        raise HTTPException(422, "Password is too long (72 bytes maximum).")

hash_pw = lambda p: bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def log(s, level, msg):
    try:
        s.add(Log(level=level, msg=msg[:300]))
        s.commit()
    except Exception:
        pass

import threading, sys
_init_lock = threading.Lock()
_ready = False
_init_error = DB_ERROR

def _redact(m):
    return re.sub(r"postgres\w*(\+\w+)?://\S+", "<db-url>", str(m))

def init_db():
    """Create/upgrade tables and seed the admin. Safe to call repeatedly; retried until it succeeds
    (a sleeping Neon database can fail the very first connection)."""
    global _ready, _init_error
    if _ready:
        return True
    if DB_ERROR:
        _init_error = DB_ERROR
        return False
    with _init_lock:
        if _ready:
            return True
        try:
            migrate()
            with Session() as s:
                if config.ADMIN_EMAIL and config.ADMIN_PASSWORD:
                    if not s.query(User).filter_by(email=config.ADMIN_EMAIL.strip().lower()).first():
                        s.add(User(email=config.ADMIN_EMAIL.strip().lower(), name="System Admin",
                                   pw=hash_pw(config.ADMIN_PASSWORD), role="admin"))
                        s.commit()
            _ready, _init_error = True, None
        except Exception as e:
            _init_error = type(e).__name__
            print("DB init failed:", type(e).__name__, _redact(e), file=sys.stderr)
        return _ready

init_db()

@app.middleware("http")
async def no_store_api(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"      # never cache account or quiz data
    return resp

@app.middleware("http")
async def db_guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health" and not _ready and not init_db():
        return JSONResponse({"detail": f"Database is not reachable ({_init_error}). Check DATABASE_URL in your hosting settings, then see /api/health."}, 503)
    return await call_next(request)


CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["Permissions-Policy"] = "camera=(), geolocation=(), payment=(), microphone=(self)"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    """Cookie sessions are SameSite=Lax; on top of that every state-changing call that relies on the cookie
    must carry our custom header, which other websites cannot add to a cross-site request."""
    if (request.url.path.startswith("/api/") and request.url.path not in ("/api/auth/login", "/api/auth/register")
            and request.method in ("POST", "PUT", "DELETE", "PATCH")
            and request.cookies.get(COOKIE) and not request.headers.get("authorization")
            and request.headers.get("x-requested-with") != "CrossMind"):
        return JSONResponse({"detail": "Request blocked."}, 403)
    return await call_next(request)

_hits = collections.defaultdict(collections.deque)
RATE_RULES = [("/api/auth/login", 20, 60), ("/api/auth/register", 8, 600), ("/api/quizzes/generate", 20, 60),
              ("/api/crosswords/generate", 20, 60), ("/api/documents/analyze", 20, 60)]

def _limited(key, limit, window):
    now_ = time.time(); q = _hits[key]
    while q and q[0] < now_ - window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now_)
    return False

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and config.RATE_LIMIT_ON and request.method != "OPTIONS":
        if len(_hits) > 20000:
            _hits.clear()
        ip = client_ip(request)
        for prefix, limit, window in RATE_RULES:
            if path == prefix and _limited(f"{ip}|{prefix}", limit, window):
                return JSONResponse({"detail": "Too many requests. Please slow down and try again shortly."}, 429, headers={"Retry-After": str(window)})
        if _limited(f"{ip}|all", 300, 60):
            return JSONResponse({"detail": "Too many requests. Please slow down and try again shortly."}, 429, headers={"Retry-After": "60"})
    if path == "/api/documents/analyze" and int(request.headers.get("content-length") or 0) > config.MAX_BYTES + 2 * 1024 * 1024:
        return JSONResponse({"detail": f"Uploads are limited to {config.MAX_UPLOAD_MB} MB in total."}, 413)
    return await call_next(request)

@app.middleware("http")
async def restore_original_path(request: Request, call_next):
    """Vercel may hand the app the rewritten function path (/api/index.py) instead of the URL the
    browser asked for. vercel.json passes the real path along as ?__p=..., so put it back before routing.
    (Registered after the other middleware so it runs first.)"""
    if request.scope["path"].endswith("/index.py"):
        pairs = parse_qsl(request.scope.get("query_string", b"").decode(), keep_blank_values=True)
        orig = next((v for k, v in pairs if k == "__p"), None)
        if orig and orig.startswith("/api/"):
            request.scope["path"] = orig
            request.scope["raw_path"] = orig.encode()
            request.scope["query_string"] = urlencode([(k, v) for k, v in pairs if k != "__p"]).encode()
    return await call_next(request)

@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, e: StarletteHTTPException):
    body = {"detail": e.detail}
    if e.status_code == 404 and e.detail == "Not Found":
        body["path"] = request.url.path          # helps diagnose hosting/routing problems
    return JSONResponse(body, e.status_code, headers=getattr(e, "headers", None))

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, e: RequestValidationError):
    first = (e.errors() or [{}])[0]
    field = str(([x for x in first.get("loc", []) if isinstance(x, str)] or ["input"])[-1]).replace("_", " ")
    kind = first.get("type", "")
    if field == "password":
        msg = "Password must be at least 8 characters and include a letter and a number."
    elif "too_short" in kind:
        msg = f"{field.capitalize()} is too short."
    elif "too_long" in kind:
        msg = f"{field.capitalize()} is too long."
    elif "pattern" in kind:
        msg = f"Please enter a valid {field}."
    else:
        msg = f"Please check the {field} field."
    return JSONResponse({"detail": msg}, 422)

@app.get("/api/health")
def health():
    return {"ok": _ready, "database": "connected" if _ready else "error"}

@app.get("/api/config")
def public_config():
    return {"max_upload_mb": config.MAX_UPLOAD_MB, "session_hours": config.SESSION_HOURS}

@app.exception_handler(Exception)
async def err_handler(request: Request, e: Exception):
    with Session() as s:
        log(s, "error", f"{request.url.path}: {type(e).__name__}: {_redact(e)}")
    return JSONResponse({"detail": str(e) if isinstance(e, HTTPException) else "Something went wrong. Please try again."}, 500)

bearer = HTTPBearer(auto_error=False)
COOKIE = "cm_session"

def db():
    s = Session()
    try:
        yield s
    finally:
        s.close()

def me(request: Request, c=Depends(bearer), s=Depends(db)):
    token = c.credentials if c else request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Please log in.")
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Please log in again.")
    u = s.get(User, uid)
    if not u or not u.active:
        raise HTTPException(401, "Account unavailable.")
    return u

def teacher(u=Depends(me)):
    if u.role not in ("teacher", "admin"):
        raise HTTPException(403, "Teacher privileges required.")
    return u

def admin(u=Depends(me)):
    if u.role != "admin":
        raise HTTPException(403, "Admin privileges required.")
    return u

# Authentication Schemas & Routes
class Reg(Clean):
    # NOTE: there is intentionally no `role` field. Public sign-up always creates a STUDENT.
    # Any "role" sent by a client is ignored. Teachers are created by an admin only.
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=1, max_length=60)
    utm: Dict[str, str] = {}
    phone: str = Field("", max_length=20)
    roll_no: str = Field("", max_length=30)
    course: str = Field("", max_length=60)
    division: str = Field("", max_length=20)

class Login(Clean):
    email: str
    password: str

@app.post("/api/auth/register")
def register(b: Reg, s=Depends(db)):
    email = b.email.strip().lower()
    check_pw(b.password)
    if s.query(User).filter_by(email=email).first():
        raise HTTPException(400, "Email already registered.")
    utm = {k[:20]: v[:80] for k, v in list(b.utm.items())[:6] if k.startswith("utm_")}
    user = User(utm=json.dumps(utm) if utm else "", 
        email=email, name=b.name.strip(), pw=hash_pw(b.password), role="student", active=True,
        phone=b.phone.strip(), roll_no=b.roll_no.strip(), course=b.course.strip(), division=b.division.strip(),
    )
    s.add(user)
    s.commit()
    return {"ok": True, "role": user.role}

DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()

def client_ip(request: Request):
    if config.PROD:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()[:45]
    return (request.client.host if request.client else "unknown")[:45]

def _secure(request: Request):
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"

@app.post("/api/auth/login")
def login(b: Login, request: Request, response: Response, s=Depends(db)):
    if config.PROD and not config.SECRET_OK:
        raise HTTPException(503, "Server is not configured securely. The administrator must set a strong SECRET_KEY.")
    email, ip = b.email.strip().lower()[:120], client_ip(request)
    since = dt.datetime.utcnow() - dt.timedelta(minutes=15)
    if config.RATE_LIMIT_ON and (s.query(LoginAttempt).filter(LoginAttempt.email == email, LoginAttempt.ts > since).count() >= 8
                                 or s.query(LoginAttempt).filter(LoginAttempt.ip == ip, LoginAttempt.ts > since).count() >= 30):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    u = s.query(User).filter_by(email=email).first()
    ok = bcrypt.checkpw(b.password.encode()[:72], (u.pw if u else DUMMY_HASH).encode())     # same work whether or not the account exists
    if not u or not ok:
        s.add(LoginAttempt(email=email, ip=ip)); s.commit()
        s.query(LoginAttempt).filter(LoginAttempt.ts < dt.datetime.utcnow() - dt.timedelta(days=1)).delete(); s.commit()
        raise HTTPException(401, "Invalid email or password.")
    if not u.active:
        raise HTTPException(403, "This account is disabled.")
    s.query(LoginAttempt).filter(LoginAttempt.email == email).delete()
    u.last_login = dt.datetime.utcnow()
    s.commit()
    now_ = dt.datetime.utcnow()
    exp = now_ + dt.timedelta(hours=config.SESSION_HOURS)
    tok = jwt.encode({"sub": str(u.id), "role": u.role, "iat": now_, "exp": exp}, config.SECRET_KEY, algorithm="HS256")
    response.set_cookie(COOKIE, tok, max_age=int(config.SESSION_HOURS * 3600), httponly=True, secure=_secure(request), samesite="lax", path="/")
    return {"token": tok, "role": u.role, "name": u.name, "email": u.email, "id": u.id,
            "expires_at": int(exp.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}

@app.get("/api/auth/me")
def get_profile(u=Depends(me)):
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


def topic_segments(topic):
    try:
        return topic_mod.fetch_topic_segments(topic)
    except topic_mod.TopicError as e:
        raise HTTPException(422, str(e))

@app.get("/api/history")
def history(u=Depends(teacher), s=Depends(db)):
    own = lambda M: s.query(M).filter_by(**({"teacher_id": u.id} if M is Quiz else {"user_id": u.id}))
    cws = [{"id": p.id, "title": p.title, "difficulty": p.difficulty, "words": len((p.data or {}).get("clues", [])),
            "done": p.done, "score": p.score, "created": p.created.isoformat()} for p in own(Puzzle).order_by(Puzzle.id.desc()).limit(100)]
    drafts = [{"id": d_.id, "topic": d_.topic, "difficulty": d_.difficulty, "count": len(d_.questions or []), "created": d_.created.isoformat()}
              for d_ in own(QuizDraft).order_by(QuizDraft.id.desc()).limit(100)]
    quizzes = [{"id": q.id, "title": q.title, "topic": q.topic, "classroom": (s.get(Classroom, q.classroom_id).name if s.get(Classroom, q.classroom_id) else ""),
                "classroom_id": q.classroom_id, "count": len(q.questions or []), "active": bool(q.is_active), "created": q.created.isoformat()}
               for q in own(Quiz).order_by(Quiz.id.desc()).limit(100)]
    return {"crosswords": cws, "drafts": drafts, "quizzes": quizzes}

@app.get("/api/quiz-drafts/{id}")
def get_draft(id: int, u=Depends(teacher), s=Depends(db)):
    d_ = s.get(QuizDraft, id)
    if not d_ or (d_.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Draft not found.")
    return {"id": d_.id, "topic": d_.topic, "difficulty": d_.difficulty, "questions": d_.questions}

@app.delete("/api/quiz-drafts/{id}")
def delete_draft(id: int, u=Depends(teacher), s=Depends(db)):
    d_ = s.get(QuizDraft, id)
    if not d_ or (d_.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Draft not found.")
    s.delete(d_); s.commit()
    return {"ok": True}

# Document Analysis
@app.post("/api/documents/analyze")
async def analyze_documents(
    files: list[UploadFile] = File(default=[]),
    text: str = Form(""),
    topic: str = Form(""),
    u=Depends(teacher),
    s=Depends(db)
):
    segs = []
    total = 0
    for f in files:
        data = await f.read(config.MAX_BYTES + 1)
        name = re.sub(r"[^\w.\- ]", "_", os.path.basename(f.filename or "file"))
        total += len(data)
        if total > config.MAX_BYTES:
            raise HTTPException(413, f"The files together are larger than the {config.MAX_UPLOAD_MB} MB limit.")
        if os.path.splitext(name)[1].lower() not in config.EXTS:
            raise HTTPException(415, f"File type '{os.path.splitext(name)[1]}' is not supported.")
        try:
            segs += parser.parse(name, data)
        except Exception as e:
            log(s, "error", f"Parse {name}: {type(e).__name__}")
            raise HTTPException(422, f"Could not extract content from {name}.")

    if len(text) > 400_000:
        raise HTTPException(413, "Pasted text is too long. Please upload it as a file instead.")
    if text.strip():
        segs.append({"text": text.strip(), "source": "Pasted learning notes"})
    budget = config.MAX_TEXT_CHARS                     # protects the server from decompression bombs
    for sg in segs:
        sg["text"] = sg["text"][:max(budget, 0)]; budget -= len(sg["text"])
    segs = [sg for sg in segs if sg["text"].strip()]

    if topic.strip() and not segs:
        segs = topic_segments(topic)

    if files and not segs:
        raise HTTPException(422, "No readable text was found in the uploaded file. If it is a scanned or image-only PDF, upload a text-based version or paste the text instead.")
    cs = nlp.concepts(segs) if segs else []
    if len(cs) < 3:
        raise HTTPException(422, "Not enough readable text or concepts found. Please provide more detailed notes.")

    d = Doc(user_id=u.id, name=topic or (files[0].filename if files else "Study Notes"), segs=segs)
    s.add(d)
    s.commit()
    return {"doc_id": d.id, "name": d.name, "segments": len(segs), "sentences": len(list(nlp.sentences(segs))), "concepts": cs}

# Crosswords
class CrosswordGenSchema(Clean):
    doc_id: int
    difficulty: str = "medium"
    count: int = Field(15, ge=5, le=40)
    concepts: list[str] = []

def public_crossword(p, full=False):
    d = p.data
    clues = [{k: v for k, v in c.items() if full or k not in ("answer", "explanation", "source")} for c in d["clues"]]
    return {
        "id": p.id,
        "title": p.title,
        "difficulty": p.difficulty,
        "size": d["size"],
        "clues": clues,
        "done": p.done,
        "score": p.score,
        "secs": p.secs,
        "hints": p.hints,
        "created": p.created.isoformat()
    }

@app.post("/api/crosswords/generate")
def generate_crossword(b: CrosswordGenSchema, u=Depends(teacher), s=Depends(db)):
    if b.difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "Invalid difficulty")
    d = s.get(Doc, b.doc_id)
    if not d or (d.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Document not found.")
    items = {i["answer"]: i for i in nlp.build_items(d.segs, b.difficulty, b.concepts or None, limit=b.count * 3)}
    pl = crossword.generate(list(items), b.count)
    if len(pl) < 3:
        raise HTTPException(422, "Could not generate a crossword from these concepts. Try selecting more keywords.")
    for p in pl:
        p.update({k: items[p["answer"]][k] for k in ("clue", "explanation", "source")})
    p = Puzzle(user_id=u.id, title=d.name, difficulty=b.difficulty, data={"size": crossword.size(pl), "clues": pl})
    s.add(p)
    s.commit()
    return public_crossword(p)

@app.get("/api/crosswords")
def list_crosswords(u=Depends(teacher), s=Depends(db)):
    puzzles = s.query(Puzzle).filter_by(user_id=u.id).order_by(Puzzle.id.desc()).all()
    return [public_crossword(p) for p in puzzles]

@app.get("/api/crosswords/{id}")
def get_crossword(id: int, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    return public_crossword(p, full=p.done)

@app.delete("/api/crosswords/{id}")
def delete_crossword(id: int, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    s.delete(p)
    s.commit()
    return {"ok": True}

class CrosswordAns(Clean):
    answers: dict[str, str] = {}
    secs: int = 0

def grade_crossword(p, answers):
    res = []
    for c in p.data["clues"]:
        a = (answers.get(f"{c['n']}-{c['dir']}") or "").strip().upper().replace(" ", "")
        res.append((c, a, "skipped" if not a else "correct" if a == c["answer"] else "wrong"))
    return res

@app.post("/api/crosswords/{id}/check")
def check_crossword(id: int, b: CrosswordAns, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    return {f"{c['n']}-{c['dir']}": st for c, a, st in grade_crossword(p, b.answers)}

class CrosswordHint(Clean):
    n: int
    dir: str

@app.post("/api/crosswords/{id}/hint")
def hint_crossword(id: int, b: CrosswordHint, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    c = next((c for c in p.data["clues"] if c["n"] == b.n and c["dir"] == b.dir), None)
    if not c:
        raise HTTPException(404, "Clue not found.")
    p.hints = (p.hints or 0) + 1
    s.commit()
    return {"letters": c["answer"][: 1 + (1 if p.difficulty == "easy" else 0)]}

@app.post("/api/crosswords/{id}/submit")
def submit_crossword(id: int, b: CrosswordAns, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    g = grade_crossword(p, b.answers)
    ok = sum(st == "correct" for *_, st in g)
    n = len(g)
    score = max(0.0, round(100.0 * ok / n - 2.0 * (p.hints or 0), 1))
    p.done = True
    p.score = score
    p.secs = b.secs
    s.commit()
    return {
        "score": score,
        "correct": ok,
        "wrong": sum(st == "wrong" for *_, st in g),
        "skipped": sum(st == "skipped" for *_, st in g),
        "total": n,
        "hints": p.hints,
        "secs": b.secs,
        "review": [
            {
                "n": c["n"],
                "dir": c["dir"],
                "clue": c["clue"],
                "yours": a,
                "answer": c["answer"],
                "status": st,
                "explanation": c["explanation"],
                "source": c["source"]
            }
            for c, a, st in g
        ]
    }

@app.get("/api/crosswords/{id}/export", response_class=HTMLResponse)
def export_crossword(id: int, u=Depends(teacher), s=Depends(db)):
    p = s.get(Puzzle, id)
    if not p or (p.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Crossword not found.")
    d = p.data
    R, C = d["size"]
    cells = {}
    for c in d["clues"]:
        for i, ch in enumerate(c["answer"]):
            cells[(c["row"] + (i if c["dir"] == "down" else 0), c["col"] + (i if c["dir"] == "across" else 0))] = ch
    nums = {(c["row"], c["col"]): c["n"] for c in d["clues"]}

    def grid(ans):
        rows = []
        for r in range(R):
            cols = []
            for k in range(C):
                is_c = (r, k) in cells
                num = nums.get((r, k), '')
                val = cells[(r, k)] if ans and is_c else ''
                cls = 'c' if is_c else 'x'
                cols.append(f"<td class='{cls}'>{num}<b>{html.escape(str(val))}</b></td>")
            rows.append("<tr>" + "".join(cols) + "</tr>")
        return "<table>" + "".join(rows) + "</table>"

    clues_html = "".join(
        f"<h3>{t}</h3><ol>" + "".join(f"<li value={int(c['n'])}>{html.escape(str(c['clue']))}</li>" for c in d["clues"] if c["dir"] == t.lower()) + "</ol>"
        for t in ("Across", "Down")
    )
    return f"""<!doctype html><html lang=en><meta charset=utf-8><title>CrossMind: {html.escape(p.title or '')}</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:30px;color:#1e293b}}
table{{border-collapse:collapse;margin-bottom:20px}}
td{{width:34px;height:34px;font-size:9px;vertical-align:top;position:relative}}
td.c{{border:1px solid #000}}td.x{{border:0}}
b{{position:absolute;inset:8px 0 0;text-align:center;font-size:16px}}
.pb{{page-break-before:always}}
</style>
<h1>CrossMind: {html.escape(p.title or '')}</h1>
<p>Difficulty: {p.difficulty.upper()} · Created: {p.created:%d %b %Y}</p>
{grid(False)}
<div class=pb>{clues_html}</div>
<div class=pb><h2>Answer Key</h2>{grid(True)}</div>
<script>window.onload=()=>print()</script></html>"""

# Classroom Management
def generate_classroom_code():
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("0", "").replace("O", "").replace("1", "").replace("I", "") # avoid ambiguous chars
    return "".join(random.choice(chars) for _ in range(6))

class CreateClassroomSchema(Clean):
    name: str = Field(min_length=2, max_length=100)
    subject: str = Field(min_length=2, max_length=100)
    division: str = "A"
    description: str = ""

@app.post("/api/classrooms")
def create_classroom(b: CreateClassroomSchema, u=Depends(teacher), s=Depends(db)):
    code = generate_classroom_code()
    while s.query(Classroom).filter_by(code=code).first():
        code = generate_classroom_code()

    classroom = Classroom(
        teacher_id=u.id,
        name=b.name.strip(),
        subject=b.subject.strip(),
        division=b.division.strip(),
        description=b.description.strip(),
        code=code
    )
    s.add(classroom)
    s.commit()
    return {
        "id": classroom.id,
        "name": classroom.name,
        "subject": classroom.subject,
        "division": classroom.division,
        "description": classroom.description,
        "code": classroom.code,
        "created": classroom.created.isoformat()
    }

class JoinClassroomSchema(Clean):
    code: str

@app.post("/api/classrooms/join")
def join_classroom(b: JoinClassroomSchema, u=Depends(me), s=Depends(db)):
    if u.role != "student":
        raise HTTPException(403, "Only student accounts can join a classroom.")
    code = b.code.strip().upper()
    c = s.query(Classroom).filter_by(code=code).first()
    if not c:
        raise HTTPException(404, "Classroom not found. Please check the code and try again.")

    if c.teacher_id == u.id:
        raise HTTPException(400, "Teachers cannot join their own classroom as a student.")

    existing = s.query(ClassroomMember).filter_by(classroom_id=c.id, student_id=u.id).first()
    if existing:
        raise HTTPException(400, "You are already a member of this classroom.")

    s.add(ClassroomMember(classroom_id=c.id, student_id=u.id))
    s.commit()

    teacher_user = s.get(User, c.teacher_id)
    student_count = s.query(ClassroomMember).filter_by(classroom_id=c.id).count()

    return {
        "ok": True,
        "classroom": {
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "division": c.division,
            "teacher": teacher_user.name if teacher_user else "Prof. Instructor",
            "student_count": student_count
        }
    }

@app.get("/api/classrooms")
def list_classrooms(u=Depends(me), s=Depends(db)):
    if u.role in ("teacher", "admin"):
        # Classrooms owned by teacher
        cs = s.query(Classroom).filter_by(teacher_id=u.id).order_by(Classroom.id.desc()).all()
        res = []
        for c in cs:
            sc = s.query(ClassroomMember).filter_by(classroom_id=c.id).count()
            qc = s.query(Quiz).filter_by(classroom_id=c.id).count()
            res.append({
                "id": c.id,
                "name": c.name,
                "subject": c.subject,
                "division": c.division,
                "description": c.description,
                "code": c.code,
                "student_count": sc,
                "quiz_count": qc,
                "created": c.created.isoformat()
            })
        return res
    else:
        # Classrooms joined by student
        memberships = s.query(ClassroomMember).filter_by(student_id=u.id).all()
        res = []
        for m in memberships:
            c = s.get(Classroom, m.classroom_id)
            if c:
                teacher_user = s.get(User, c.teacher_id)
                sc = s.query(ClassroomMember).filter_by(classroom_id=c.id).count()
                active_quiz = s.query(Quiz).filter_by(classroom_id=c.id, is_active=True).first()
                res.append({
                    "id": c.id,
                    "name": c.name,
                    "subject": c.subject,
                    "division": c.division,
                    "description": c.description,
                    "teacher": teacher_user.name if teacher_user else "Prof. Instructor",
                    "student_count": sc,
                    "has_active_quiz": bool(active_quiz),
                    "active_quiz_id": active_quiz.id if active_quiz else None,
                    "joined_at": m.joined_at.isoformat()
                })
        return res

@app.get("/api/classrooms/{id}")
def get_classroom_details(id: int, u=Depends(me), s=Depends(db)):
    c = s.get(Classroom, id)
    if not c:
        raise HTTPException(404, "Classroom not found.")

    is_teacher = (c.teacher_id == u.id or u.role == "admin")
    is_member = s.query(ClassroomMember).filter_by(classroom_id=c.id, student_id=u.id).first() is not None

    if not is_teacher and not is_member:
        raise HTTPException(403, "You are not a member of this classroom.")

    teacher_user = s.get(User, c.teacher_id)
    students = [
        {"id": st.id, "name": st.name, "email": st.email}
        for st in s.query(User).join(ClassroomMember, ClassroomMember.student_id == User.id).filter(ClassroomMember.classroom_id == c.id).all()
    ]

    quizzes = s.query(Quiz).filter_by(classroom_id=c.id).order_by(Quiz.id.desc()).all()
    quiz_list = []
    for q in quizzes:
        attempts = s.query(QuizAttempt).filter_by(quiz_id=q.id).all()
        my_attempt = s.query(QuizAttempt).filter_by(quiz_id=q.id, student_id=u.id).first()
        quiz_list.append({
            "id": q.id,
            "title": q.title,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "time_limit": q.time_limit,
            "question_count": len(q.questions),
            "is_active": q.is_active,
            "started_at": q.started_at.isoformat() if q.started_at else None,
            "attempts_count": len(attempts),
            "my_status": "completed" if my_attempt else ("active" if q.is_active else "assigned"),
            "my_score": my_attempt.percentage if my_attempt else None
        })

    return {
        "id": c.id,
        "name": c.name,
        "subject": c.subject,
        "division": c.division,
        "description": c.description,
        "code": c.code if is_teacher else None,
        "teacher": teacher_user.name if teacher_user else "Prof. Instructor",
        "student_count": len(students),
        "students": students if is_teacher else [],
        "quizzes": quiz_list,
        "is_teacher": is_teacher
    }

@app.delete("/api/classrooms/{id}/students/{student_id}")
def remove_student_from_classroom(id: int, student_id: int, u=Depends(teacher), s=Depends(db)):
    c = s.get(Classroom, id)
    if not c or (c.teacher_id != u.id and u.role != "admin"):
        raise HTTPException(403, "Not allowed.")
    m = s.query(ClassroomMember).filter_by(classroom_id=c.id, student_id=student_id).first()
    if m:
        s.delete(m)
        s.commit()
    return {"ok": True}

# Quiz Generation, Management & Live Competition
class QuizGenSchema(Clean):
    doc_id: Optional[int] = None
    topic: str = "General Quiz"
    text: str = Field("", max_length=400000)
    difficulty: str = "medium"
    count: int = Field(15, ge=5, le=40)
    question_types: List[str] = ["mcq", "true_false", "msq"]

@app.post("/api/quizzes/generate")
def generate_quiz(b: QuizGenSchema, u=Depends(teacher), s=Depends(db)):
    segs = []
    if b.doc_id:
        doc = s.get(Doc, b.doc_id)
        if doc:
            segs = doc.segs
    if not segs and b.text.strip():
        segs = [{"text": b.text.strip(), "source": "Provided Notes"}]
    if not segs and b.topic.strip() and b.topic.strip() != "General Quiz":
        segs = topic_segments(b.topic)
    if not segs:
        raise HTTPException(422, "Provide a topic, paste notes, or upload a file.")
    if len(nlp.concepts(segs)) < 3:
        raise HTTPException(422, "Not enough readable material to build a quiz. Please provide more detailed notes.")

    questions = quiz_generator.generate_quiz_questions(
        segs=segs,
        topic=b.topic,
        difficulty=b.difficulty,
        count=b.count,
        q_types=b.question_types
    )

    seen_q, uniq = set(), []
    for q_ in questions:
        k = re.sub(r"\W+", " ", q_["question"].lower()).strip()
        if k not in seen_q:
            seen_q.add(k); uniq.append(q_)
    questions = uniq
    if not questions:
        raise HTTPException(422, "Could not generate quiz questions from supplied material.")
    draft = QuizDraft(user_id=u.id, topic=b.topic.strip() or "Quiz", difficulty=b.difficulty, questions=questions)
    s.add(draft); s.commit()

    return {
        "draft_id": draft.id,
        "topic": b.topic,
        "difficulty": b.difficulty,
        "count": len(questions),
        "questions": questions
    }

class CreateQuizSchema(Clean):
    classroom_id: int
    doc_id: Optional[int] = None
    title: str = Field(min_length=2, max_length=100)
    topic: str = Field(min_length=2, max_length=100)
    difficulty: str = "medium"
    time_limit: int = Field(15, ge=1, le=180) # minutes
    questions: List[Dict[str, Any]] = Field(max_length=100)
    controls: Dict[str, Any] = {
        "randomize_questions": True,
        "randomize_options": True,
        "allow_hints": True,
        "show_answers": True,
        "show_leaderboard": True,
        "leaderboard_privacy": "full" # full, top3, my_rank, hidden
    }

@app.post("/api/quizzes")
def create_and_assign_quiz(b: CreateQuizSchema, u=Depends(teacher), s=Depends(db)):
    c = s.get(Classroom, b.classroom_id)
    if not c or (c.teacher_id != u.id and u.role != "admin"):
        raise HTTPException(403, "Not allowed for this classroom.")

    quiz = Quiz(
        teacher_id=u.id,
        classroom_id=c.id,
        doc_id=b.doc_id,
        title=b.title.strip(),
        topic=b.topic.strip(),
        difficulty=b.difficulty,
        time_limit=b.time_limit,
        questions=b.questions,
        controls=b.controls,
        is_active=False
    )
    s.add(quiz)
    s.commit()
    return {"id": quiz.id, "title": quiz.title, "classroom": c.name, "created": quiz.created.isoformat()}

@app.post("/api/quizzes/{id}/start")
def start_quiz(id: int, u=Depends(teacher), s=Depends(db)):
    q = s.get(Quiz, id)
    if not q or (q.teacher_id != u.id and u.role != "admin"):
        raise HTTPException(403, "Not allowed.")
    q.is_active = True
    q.started_at = dt.datetime.utcnow()
    s.commit()
    return {"ok": True, "quiz_id": q.id, "is_active": True, "started_at": q.started_at.isoformat()}

@app.post("/api/quizzes/{id}/end")
def end_quiz(id: int, u=Depends(teacher), s=Depends(db)):
    q = s.get(Quiz, id)
    if not q or (q.teacher_id != u.id and u.role != "admin"):
        raise HTTPException(403, "Not allowed.")
    q.is_active = False
    q.ended_at = dt.datetime.utcnow()
    s.commit()
    return {"ok": True, "quiz_id": q.id, "is_active": False}

@app.get("/api/quizzes/{id}")
def get_quiz(id: int, u=Depends(me), s=Depends(db)):
    q = s.get(Quiz, id)
    if not q:
        raise HTTPException(404, "Quiz not found.")

    c = s.get(Classroom, q.classroom_id)
    is_teacher = (q.teacher_id == u.id or u.role == "admin")
    is_member = s.query(ClassroomMember).filter_by(classroom_id=q.classroom_id, student_id=u.id).first() is not None

    if not is_teacher and not is_member:
        raise HTTPException(403, "You do not have access to this quiz.")

    attempt = s.query(QuizAttempt).filter_by(quiz_id=q.id, student_id=u.id).first()

    # Sanitize questions for student taking quiz (strip answers/explanations if not yet submitted)
    sanitized_questions = []
    for q_item in q.questions:
        q_copy = dict(q_item)
        if not is_teacher and not attempt:
            q_copy.pop("answer", None)
            q_copy.pop("explanation", None)
            q_copy.pop("source", None)
        sanitized_questions.append(q_copy)

    return {
        "id": q.id,
        "title": q.title,
        "topic": q.topic,
        "difficulty": q.difficulty,
        "time_limit": q.time_limit,
        "is_active": q.is_active,
        "classroom_name": c.name if c else "Classroom",
        "controls": q.controls,
        "questions": sanitized_questions,
        "submitted": bool(attempt),
        "my_attempt": {
            "score": attempt.score,
            "percentage": attempt.percentage,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "time_taken_secs": attempt.time_taken_secs,
            "answers": attempt.answers,
            "submitted_at": attempt.submitted_at.isoformat()
        } if attempt else None
    }

class SubmitQuizSchema(Clean):
    answers: Dict[str, Any] # {q_id: answer_value}
    time_taken_secs: int = 0

@app.post("/api/quizzes/{id}/submit")
def submit_quiz(id: int, b: SubmitQuizSchema, u=Depends(me), s=Depends(db)):
    q = s.get(Quiz, id)
    if not q:
        raise HTTPException(404, "Quiz not found.")
    if u.role != "student" or not s.query(ClassroomMember).filter_by(classroom_id=q.classroom_id, student_id=u.id).first():
        raise HTTPException(403, "Only students enrolled in this classroom can submit this quiz.")
    if not q.is_active:
        raise HTTPException(400, "This quiz is not open for submissions.")

    existing = s.query(QuizAttempt).filter_by(quiz_id=q.id, student_id=u.id).first()
    if existing:
        raise HTTPException(400, "You have already submitted this quiz.")

    correct = 0
    wrong = 0
    unanswered = 0
    total_q = len(q.questions)
    review_items = []

    for item in q.questions:
        qid = str(item["id"])
        user_ans = b.answers.get(qid)
        actual_ans = item["answer"]

        if user_ans is None or user_ans == "" or user_ans == []:
            status = "unanswered"
            unanswered += 1
        elif isinstance(actual_ans, list):
            # MSQ
            if isinstance(user_ans, list) and sorted([str(x).upper() for x in user_ans]) == sorted([str(x).upper() for x in actual_ans]):
                status = "correct"
                correct += 1
            else:
                status = "wrong"
                wrong += 1
        else:
            # MCQ or True/False
            if str(user_ans).strip().upper() == str(actual_ans).strip().upper():
                status = "correct"
                correct += 1
            else:
                status = "wrong"
                wrong += 1

        review_items.append({
            "id": item["id"],
            "question": item["question"],
            "type": item.get("type", "mcq"),
            "options": item.get("options", []),
            "your_answer": user_ans,
            "correct_answer": actual_ans,
            "status": status,
            "explanation": item.get("explanation", ""),
            "source": item.get("source", "")
        })

    pct = round(100.0 * correct / total_q, 1) if total_q > 0 else 0.0

    attempt = QuizAttempt(
        quiz_id=q.id,
        student_id=u.id,
        score=float(correct),
        percentage=pct,
        correct_count=correct,
        wrong_count=wrong,
        unanswered_count=unanswered,
        time_taken_secs=b.time_taken_secs,
        answers=b.answers
    )
    s.add(attempt)
    s.commit()

    # Calculate student rank in this quiz
    all_attempts = s.query(QuizAttempt).filter_by(quiz_id=q.id).order_by(
        QuizAttempt.percentage.desc(),
        QuizAttempt.time_taken_secs.asc(),
        QuizAttempt.submitted_at.asc()
    ).all()

    rank = 1
    for idx, att in enumerate(all_attempts, 1):
        if att.student_id == u.id:
            rank = idx
            break

    return {
        "percentage": pct,
        "correct": correct,
        "wrong": wrong,
        "unanswered": unanswered,
        "total": total_q,
        "time_taken_secs": b.time_taken_secs,
        "rank": rank,
        "review": review_items
    }

# Leaderboard & Live Results
@app.get("/api/quizzes/{id}/live-leaderboard")
def live_quiz_leaderboard(id: int, u=Depends(me), s=Depends(db)):
    q = s.get(Quiz, id)
    if not q:
        raise HTTPException(404, "Quiz not found.")

    c = s.get(Classroom, q.classroom_id)
    is_teacher = (q.teacher_id == u.id or u.role == "admin")
    if not is_teacher and not s.query(ClassroomMember).filter_by(classroom_id=q.classroom_id, student_id=u.id).first():
        raise HTTPException(403, "You do not have access to this leaderboard.")

    # Get all attempts sorted according to tie-breaking logic:
    # 1. Higher percentage
    # 2. Faster completion time (time_taken_secs)
    # 3. Earlier submission timestamp
    attempts = s.query(QuizAttempt).filter_by(quiz_id=q.id).order_by(
        QuizAttempt.percentage.desc(),
        QuizAttempt.time_taken_secs.asc(),
        QuizAttempt.submitted_at.asc()
    ).all()

    members_count = s.query(ClassroomMember).filter_by(classroom_id=q.classroom_id).count()

    leaderboard_data = []
    my_rank_info = None

    for rank, att in enumerate(attempts, 1):
        student = s.get(User, att.student_id)
        entry = {
            "rank": rank,
            "student_id": att.student_id,
            "student_name": student.name if student else "Student",
            "score": att.correct_count,
            "total": len(q.questions),
            "percentage": att.percentage,
            "time_taken_secs": att.time_taken_secs,
            "submitted_at": att.submitted_at.strftime("%H:%M:%S")
        }
        leaderboard_data.append(entry)
        if att.student_id == u.id:
            my_rank_info = entry

    privacy = (q.controls or {}).get("leaderboard_privacy", "full")
    
    if not is_teacher:
        if privacy == "hidden":
            leaderboard_data = []
        elif privacy == "top3":
            leaderboard_data = leaderboard_data[:3]
        elif privacy == "my_rank" and my_rank_info:
            leaderboard_data = [my_rank_info]

    return {
        "quiz_id": q.id,
        "quiz_title": q.title,
        "classroom_name": c.name if c else "Classroom",
        "total_students": members_count,
        "completed_students": len(attempts),
        "is_active": q.is_active,
        "leaderboard": leaderboard_data,
        "my_rank": my_rank_info
    }

# Classroom Leaderboard
@app.get("/api/classrooms/{id}/leaderboard")
def classroom_overall_leaderboard(id: int, u=Depends(me), s=Depends(db)):
    c = s.get(Classroom, id)
    if not c:
        raise HTTPException(404, "Classroom not found.")
    if c.teacher_id != u.id and u.role != "admin" and not s.query(ClassroomMember).filter_by(classroom_id=c.id, student_id=u.id).first():
        raise HTTPException(403, "You do not have access to this classroom.")

    quizzes = s.query(Quiz).filter_by(classroom_id=c.id).all()
    quiz_ids = [q.id for q in quizzes]

    students = s.query(User).join(ClassroomMember, ClassroomMember.student_id == User.id).filter(ClassroomMember.classroom_id == c.id).all()

    student_stats = []
    for st in students:
        attempts = s.query(QuizAttempt).filter(QuizAttempt.quiz_id.in_(quiz_ids), QuizAttempt.student_id == st.id).all() if quiz_ids else []
        total_quizzes = len(attempts)
        avg_pct = round(sum(a.percentage for a in attempts) / total_quizzes, 1) if total_quizzes > 0 else 0.0
        total_time = sum(a.time_taken_secs for a in attempts)
        student_stats.append({
            "student_id": st.id,
            "name": st.name,
            "quizzes_completed": total_quizzes,
            "avg_percentage": avg_pct,
            "total_time_secs": total_time
        })

    # Sort leaderboard: Highest average score -> lowest total time
    student_stats.sort(key=lambda x: (-x["avg_percentage"], x["total_time_secs"]))

    for idx, item in enumerate(student_stats, 1):
        item["rank"] = idx

    return {
        "classroom_id": c.id,
        "classroom_name": c.name,
        "total_students": len(students),
        "leaderboard": student_stats
    }

# Analytics & Student Performance
@app.get("/api/classrooms/{id}/analytics")
def teacher_classroom_analytics(id: int, u=Depends(teacher), s=Depends(db)):
    c = s.get(Classroom, id)
    if not c or (c.teacher_id != u.id and u.role != "admin"):
        raise HTTPException(403, "Not allowed.")

    quizzes = s.query(Quiz).filter_by(classroom_id=c.id).all()
    quiz_ids = [q.id for q in quizzes]
    total_students = s.query(ClassroomMember).filter_by(classroom_id=c.id).count()

    all_attempts = s.query(QuizAttempt).filter(QuizAttempt.quiz_id.in_(quiz_ids)).all() if quiz_ids else []

    avg_score = round(sum(a.percentage for a in all_attempts) / len(all_attempts), 1) if all_attempts else 0.0
    highest_score = max([a.percentage for a in all_attempts], default=0.0)
    lowest_score = min([a.percentage for a in all_attempts], default=0.0)

    # Question accuracy breakdown across quizzes
    question_stats = []
    for q in quizzes:
        attempts = s.query(QuizAttempt).filter_by(quiz_id=q.id).all()
        if not attempts:
            continue
        for item in q.questions:
            qid = str(item["id"])
            correct_count = 0
            for att in attempts:
                ans = att.answers.get(qid)
                if ans and str(ans).strip().upper() == str(item["answer"]).strip().upper():
                    correct_count += 1
            acc_pct = round(100.0 * correct_count / len(attempts), 1)
            question_stats.append({
                "quiz_title": q.title,
                "question": item["question"][:60] + "...",
                "accuracy_percentage": acc_pct
            })

    return {
        "total_students": total_students,
        "total_quizzes": len(quizzes),
        "total_attempts": len(all_attempts),
        "average_score": avg_score,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "participation_rate": round(100.0 * len(all_attempts) / (total_students * len(quizzes)), 1) if (total_students * len(quizzes)) > 0 else 0.0,
        "question_accuracy": question_stats[:10]
    }

@app.get("/api/student/performance")
def student_performance_analytics(u=Depends(me), s=Depends(db)):
    attempts = s.query(QuizAttempt).filter_by(student_id=u.id).order_by(QuizAttempt.submitted_at.desc()).all()

    total_quizzes = len(attempts)
    avg_score = round(sum(a.percentage for a in attempts) / total_quizzes, 1) if total_quizzes > 0 else 0.0
    best_score = max([a.percentage for a in attempts], default=0.0)

    history = []
    for a in attempts:
        q = s.get(Quiz, a.quiz_id)
        c = s.get(Classroom, q.classroom_id) if q else None
        history.append({
            "quiz_title": q.title if q else "Quiz",
            "classroom_name": c.name if c else "Classroom",
            "score_percentage": a.percentage,
            "correct": a.correct_count,
            "total": (a.correct_count + a.wrong_count + a.unanswered_count),
            "date": a.submitted_at.strftime("%b %d, %Y")
        })

    by_topic = collections.defaultdict(list)
    for a_ in attempts:
        q_ = s.get(Quiz, a_.quiz_id)
        if q_ and q_.topic:
            by_topic[q_.topic].append(a_.percentage)
    topic_avg = {t: sum(v) / len(v) for t, v in by_topic.items()}
    strong = [t for t, v in sorted(topic_avg.items(), key=lambda x: -x[1]) if v >= 70][:6]
    weak = [t for t, v in sorted(topic_avg.items(), key=lambda x: x[1]) if v < 60][:6]

    return {
        "average_score": avg_score,
        "best_score": best_score,
        "quizzes_completed": total_quizzes,
        "classrooms_joined": s.query(ClassroomMember).filter_by(student_id=u.id).count(),
        "strong_topics": strong,
        "needs_practice": weak,
        "history": history
    }

# Admin Platform Endpoints
@app.get("/api/admin/dashboard")
def admin_dashboard(a=Depends(admin), s=Depends(db)):
    puzzles = s.query(Puzzle).all()
    quizzes = s.query(Quiz).all()
    attempts = s.query(QuizAttempt).all()
    classrooms = s.query(Classroom).all()
    users = s.query(User).all()

    return {
        "users": len(users),
        "teachers": len([u for u in users if u.role == "teacher"]),
        "students": len([u for u in users if u.role == "student"]),
        "classrooms": len(classrooms),
        "quizzes": len(quizzes),
        "crosswords": len(puzzles),
        "quiz_attempts": len(attempts),
        "avg_quiz_score": round(sum(a.percentage for a in attempts) / len(attempts), 1) if attempts else 0.0
    }

EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PROFILE_FIELDS = ("phone", "employee_id", "department", "subject", "roll_no", "course", "division")

def user_dict(u, s=None, detail=False):
    d = {
        "id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active,
        "phone": u.phone or "", "employee_id": u.employee_id or "", "department": u.department or "",
        "subject": u.subject or "", "roll_no": u.roll_no or "", "course": u.course or "", "division": u.division or "",
        "joined": u.created.strftime("%Y-%m-%d") if u.created else "",
        "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never",
        "self_registered": u.created_by is None,
    }
    if s is not None:
        if u.role == "teacher":
            d["classrooms"] = s.query(Classroom).filter_by(teacher_id=u.id).count()
            d["quizzes"] = s.query(Quiz).filter_by(teacher_id=u.id).count()
        elif u.role == "student":
            d["classrooms"] = s.query(ClassroomMember).filter_by(student_id=u.id).count()
            d["quizzes"] = s.query(QuizAttempt).filter_by(student_id=u.id).count()
    return d

def purge_user(s, u):
    """Delete a user and everything that references them (works for teachers and students)."""
    if u.role == "teacher":
        for c in s.query(Classroom).filter_by(teacher_id=u.id).all():
            for q in s.query(Quiz).filter_by(classroom_id=c.id).all():
                s.query(QuizAttempt).filter_by(quiz_id=q.id).delete()
                s.delete(q)
            s.query(ClassroomMember).filter_by(classroom_id=c.id).delete()
            s.delete(c)
        for q in s.query(Quiz).filter_by(teacher_id=u.id).all():
            s.query(QuizAttempt).filter_by(quiz_id=q.id).delete()
            s.delete(q)
    s.query(QuizAttempt).filter_by(student_id=u.id).delete()
    s.query(ClassroomMember).filter_by(student_id=u.id).delete()
    s.query(Puzzle).filter_by(user_id=u.id).delete()
    s.query(Doc).filter_by(user_id=u.id).delete()
    s.delete(u)

class AdminUserSchema(Clean):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(pattern=EMAIL_RE)
    password: str = Field(min_length=6)
    phone: str = Field("", max_length=20)
    employee_id: str = Field("", max_length=30)
    department: str = Field("", max_length=80)
    subject: str = Field("", max_length=80)
    roll_no: str = Field("", max_length=30)
    course: str = Field("", max_length=60)
    division: str = Field("", max_length=20)

class AdminUserUpdate(Clean):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    email: Optional[str] = Field(None, pattern=EMAIL_RE)
    password: Optional[str] = Field(None, min_length=6)   # only set to reset the password
    active: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    employee_id: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, max_length=80)
    subject: Optional[str] = Field(None, max_length=80)
    roll_no: Optional[str] = Field(None, max_length=30)
    course: Optional[str] = Field(None, max_length=60)
    division: Optional[str] = Field(None, max_length=20)

def admin_create_user(b, role, a, s):
    email = b.email.strip().lower()
    check_pw(b.password)
    if s.query(User).filter_by(email=email).first():
        raise HTTPException(400, "A user with this email already exists.")
    user = User(email=email, name=b.name.strip(), pw=hash_pw(b.password), role=role, active=True, created_by=a.id)
    for f in PROFILE_FIELDS:
        setattr(user, f, (getattr(b, f, "") or "").strip())
    s.add(user)
    s.commit()
    log(s, "info", f"Admin {a.email} created {role} {user.email}")
    return {"ok": True, **user_dict(user, s)}

@app.post("/api/admin/teachers")
def admin_create_teacher(b: AdminUserSchema, a=Depends(admin), s=Depends(db)):
    return admin_create_user(b, "teacher", a, s)

@app.post("/api/admin/students")
def admin_create_student(b: AdminUserSchema, a=Depends(admin), s=Depends(db)):
    return admin_create_user(b, "student", a, s)

@app.get("/api/admin/users")
def admin_list_users(role: Optional[str] = None, q: str = "", a=Depends(admin), s=Depends(db)):
    qry = s.query(User)
    if role in ("student", "teacher", "admin"):
        qry = qry.filter(User.role == role)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        from sqlalchemy import or_, func
        qry = qry.filter(or_(func.lower(User.name).like(like), func.lower(User.email).like(like),
                             func.lower(User.roll_no).like(like), func.lower(User.employee_id).like(like),
                             func.lower(User.department).like(like)))
    return [user_dict(u, s) for u in qry.order_by(User.id.desc()).all()]

@app.get("/api/admin/users/{id}")
def admin_get_user(id: int, a=Depends(admin), s=Depends(db)):
    u = s.get(User, id)
    if not u:
        raise HTTPException(404, "User not found.")
    return user_dict(u, s)

@app.put("/api/admin/users/{id}")
def admin_update_user(id: int, b: AdminUserUpdate, a=Depends(admin), s=Depends(db)):
    u = s.get(User, id)
    if not u:
        raise HTTPException(404, "User not found.")
    if u.role == "admin" and u.id != a.id:
        raise HTTPException(403, "Other admin accounts cannot be edited here.")
    if b.active is False and u.id == a.id:
        raise HTTPException(400, "You cannot disable your own account.")
    if b.email is not None:
        email = b.email.strip().lower()
        if email != u.email and s.query(User).filter_by(email=email).first():
            raise HTTPException(400, "Another user already uses this email.")
        u.email = email
    if b.name is not None:
        u.name = b.name.strip()
    if b.password:
        check_pw(b.password)
        u.pw = hash_pw(b.password)
    if b.active is not None:
        u.active = b.active
    for f in PROFILE_FIELDS:
        v = getattr(b, f)
        if v is not None:
            setattr(u, f, v.strip())
    u.updated = dt.datetime.utcnow()
    s.commit()
    log(s, "info", f"Admin {a.email} updated {u.role} {u.email}")
    return {"ok": True, **user_dict(u, s)}

@app.post("/api/admin/users/{id}/toggle")
def admin_toggle_user(id: int, a=Depends(admin), s=Depends(db)):
    u = s.get(User, id)
    if not u or u.id == a.id or u.role == "admin":
        raise HTTPException(400, "Operation not allowed.")
    u.active = not u.active
    u.updated = dt.datetime.utcnow()
    s.commit()
    return {"active": u.active}

@app.delete("/api/admin/users/{id}")
def admin_delete_user(id: int, a=Depends(admin), s=Depends(db)):
    u = s.get(User, id)
    if not u or u.id == a.id or u.role == "admin":
        raise HTTPException(400, "Operation not allowed.")
    email, role = u.email, u.role
    purge_user(s, u)
    s.commit()
    log(s, "info", f"Admin {a.email} deleted {role} {email}")
    return {"ok": True}

CSV_COLS = ["name", "email", "phone", "employee_id", "department", "subject", "roll_no", "course", "division", "active", "joined", "last_login"]

@app.get("/api/admin/export")
def admin_export(role: str = "teacher", a=Depends(admin), s=Depends(db)):
    if role not in ("teacher", "student"):
        raise HTTPException(400, "role must be teacher or student")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLS)
    for u in s.query(User).filter_by(role=role).order_by(User.id).all():
        d = user_dict(u)
        w.writerow([("'" + str(d[c])) if str(d[c])[:1] in ("=", "+", "-", "@", "\t", "\r") else d[c] for c in CSV_COLS])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={role}s.csv"})

@app.post("/api/admin/import")
async def admin_import(role: str = Form("teacher"), file: UploadFile = File(...), a=Depends(admin), s=Depends(db)):
    """Bulk-create teachers/students from CSV. Columns: name,email,password (+ optional profile columns)."""
    if role not in ("teacher", "student"):
        raise HTTPException(400, "role must be teacher or student")
    raw = (await file.read(config.MAX_BYTES + 1)).decode("utf-8-sig", errors="ignore")
    created, skipped = 0, []
    for i, row in enumerate(csv.DictReader(io.StringIO(raw)), start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email, name, pw = row.get("email", "").lower(), row.get("name", ""), row.get("password", "")
        import re as _re
        if not name or not _re.match(EMAIL_RE, email) or len(pw) < 8 or len(pw) > 72 or not _re.search(r"[A-Za-z]", pw) or not _re.search(r"\d", pw):
            skipped.append(f"row {i}: needs name, valid email, password (8+ chars with a letter and a number)")
            continue
        if s.query(User).filter_by(email=email).first():
            skipped.append(f"row {i}: {email} already exists")
            continue
        u = User(email=email, name=name, pw=hash_pw(pw), role=role, active=True, created_by=a.id)
        for f in PROFILE_FIELDS:
            setattr(u, f, row.get(f, ""))
        s.add(u)
        created += 1
    s.commit()
    log(s, "info", f"Admin {a.email} imported {created} {role}(s)")
    return {"created": created, "skipped": skipped}

@app.get("/api/admin/logs")
def admin_logs(a=Depends(admin), s=Depends(db)):
    return [
        {"level": l.level, "msg": l.msg, "at": l.created.strftime("%Y-%m-%d %H:%M")}
        for l in s.query(Log).order_by(Log.id.desc()).limit(100).all()
    ]

# Mount static frontend
_ui = os.path.join(os.path.dirname(__file__), "..", "public")
if os.path.isdir(_ui) and not os.getenv("VERCEL"):
    app.mount("/", StaticFiles(directory=_ui, html=True), name="ui")
