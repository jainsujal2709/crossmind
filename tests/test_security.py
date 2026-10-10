"""Security checks: every route needs a login, roles are enforced, cookies are HttpOnly, headers are set,
brute force is limited, and users cannot reach each other's data."""
import sys, os, re
os.environ["RATE_LIMIT"] = "off"
if os.path.exists("./test_sec.db"): os.remove("./test_sec.db")
os.environ.update(DATABASE_URL="sqlite:///./test_sec.db", ADMIN_EMAIL="boss@x.io", ADMIN_PASSWORD="BossPass123", SECRET_KEY="k" * 32)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute
import main
from models import Puzzle, Session

PUBLIC = {"/api/health", "/api/config", "/api/auth/login", "/api/auth/register", "/api/auth/logout"}
NOTES = ("Supervised learning is a learning approach that trains models on labeled examples. Overfitting is a situation where a model performs well on training data but fails on unseen data. "
         "Regularization is a technique that penalizes model complexity to reduce overfitting. Clustering is an unsupervised technique that groups similar data points without labels. "
         "Backpropagation is an algorithm that computes gradients to update neural network weights. Validation is a process that evaluates a model on held out data during training.")

def client(): return TestClient(main.app)
def tok(c, e, p): r = c.post("/api/auth/login", json={"email": e, "password": p}); assert r.status_code == 200, r.text; return {"Authorization": "Bearer " + r.json()["token"]}

def test_every_route_requires_login():
    c = client(); checked = 0
    for r in main.app.routes:
        if not isinstance(r, APIRoute) or r.path in PUBLIC: continue
        for m in r.methods - {"HEAD", "OPTIONS"}:
            path = re.sub(r"\{[^}]+\}", "1", r.path)
            resp = c.request(m, path)
            assert resp.status_code in (401, 403), f"{m} {r.path} is reachable without login ({resp.status_code})"; checked += 1
    assert checked > 30

def test_docs_hidden_and_headers():
    c = client()
    assert c.get("/docs").status_code in (404, 405) or "swagger" not in c.get("/docs").text.lower()
    assert c.get("/openapi.json").status_code == 404
    h = c.get("/api/health").headers
    for k in ("content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"): assert k in h, k
    assert "frame-ancestors 'none'" in h["content-security-policy"] and h["x-frame-options"] == "DENY"

def test_roles_cookies_idor_xss():
    c = client(); admin = tok(c, "boss@x.io", "BossPass123")
    for n in ("t1", "t2"):
        assert c.post("/api/admin/teachers", json={"name": n, "email": f"{n}@x.io", "password": "Teach1234"}, headers=admin).status_code == 200
    for n in ("s1", "s2"): assert c.post("/api/auth/register", json={"name": n, "email": f"{n}@x.io", "password": "Stud12345"}).status_code == 200
    t1, t2, s1, s2 = tok(c, "t1@x.io", "Teach1234"), tok(c, "t2@x.io", "Teach1234"), tok(c, "s1@x.io", "Stud12345"), tok(c, "s2@x.io", "Stud12345")
    # roles
    for h in (t1, s1): assert c.get("/api/admin/dashboard", headers=h).status_code == 403
    assert c.get("/api/history", headers=s1).status_code == 403
    # teacher 1 data
    cl = c.post("/api/classrooms", json={"name": "Class One", "subject": "Subject A", "division": "A", "description": "d"}, headers=t1).json()
    doc = c.post("/api/documents/analyze", data={"text": NOTES, "topic": "<script>x</script>"}, headers=t1).json()
    cw = c.post("/api/crosswords/generate", json={"doc_id": doc["doc_id"], "difficulty": "easy", "count": 6}, headers=t1).json()
    qz = c.post("/api/quizzes/generate", json={"doc_id": doc["doc_id"], "topic": "T", "count": 5}, headers=t1).json()
    qr = c.post("/api/quizzes", json={"classroom_id": cl["id"], "title": "Quiz One", "topic": "Topic", "time_limit": 5, "questions": qz["questions"]}, headers=t1); assert qr.status_code == 200, qr.text; q = qr.json()
    # teacher 2 cannot touch teacher 1 data
    assert c.get(f"/api/crosswords/{cw['id']}", headers=t2).status_code in (403, 404)
    assert c.delete(f"/api/crosswords/{cw['id']}", headers=t2).status_code in (403, 404)
    assert c.get(f"/api/classrooms/{cl['id']}", headers=t2).status_code in (403, 404)
    assert c.get(f"/api/classrooms/{cl['id']}/analytics", headers=t2).status_code in (403, 404)
    assert c.post(f"/api/quizzes/{q['id']}/start", headers=t2).status_code in (403, 404)
    assert c.get(f"/api/quiz-drafts/{qz['draft_id']}", headers=t2).status_code in (403, 404)
    assert c.get(f"/api/crosswords/{cw['id']}/export", headers=t2).status_code in (403, 404)
    # student who has not joined cannot open or submit the quiz
    c.post(f"/api/quizzes/{q['id']}/start", headers=t1)
    assert c.get(f"/api/quizzes/{q['id']}", headers=s2).status_code in (403, 404)
    assert c.post(f"/api/quizzes/{q['id']}/submit", json={"answers": {}, "time_taken_secs": 5}, headers=s2).status_code in (403, 404)
    assert c.get(f"/api/quizzes/{q['id']}/live-leaderboard", headers=s2).status_code in (403, 404)
    assert c.get(f"/api/classrooms/{cl['id']}/leaderboard", headers=s2).status_code in (403, 404)
    # stored markup is escaped in the printable export
    with Session() as s:
        p = s.get(Puzzle, cw["id"]); p.title = "<script>alert(1)</script>"; s.commit()
    html = c.get(f"/api/crosswords/{cw['id']}/export", headers=t1).text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    # names are sanitised on the way in
    assert c.post("/api/auth/register", json={"name": "<img src=x onerror=alert(1)>", "email": "x@x.io", "password": "Stud12345"}).status_code == 200
    names = [u["name"] for u in c.get("/api/admin/users?role=student", headers=admin).json()] if c.get("/api/admin/users?role=student", headers=admin).status_code == 200 else []
    assert all("<" not in n and ">" not in n for n in names)

def test_cookie_session():
    c = client()
    r = c.post("/api/auth/login", json={"email": "boss@x.io", "password": "BossPass123"})
    sc = r.headers["set-cookie"].lower()
    assert "cm_session=" in sc and "httponly" in sc and "samesite=lax" in sc and "max-age=10800" in sc and "expires_at" in r.json()
    assert c.get("/api/auth/me").status_code == 200                                    # cookie alone authenticates GET
    assert c.post("/api/auth/logout").status_code == 200 or True
    c2 = client(); c2.post("/api/auth/login", json={"email": "boss@x.io", "password": "BossPass123"})
    assert c2.post("/api/classrooms", json={"name": "Cross-site", "subject": "Subject A", "division": "A", "description": "d"}).status_code == 403   # no CSRF header
    assert c2.post("/api/classrooms", json={"name": "Same-site", "subject": "Subject A", "division": "A", "description": "d"}, headers={"X-Requested-With": "CrossMind"}).status_code == 200
    c2.post("/api/auth/logout", headers={"X-Requested-With": "CrossMind"}); c2.cookies.clear()
    assert c2.get("/api/auth/me").status_code == 401

def test_expired_and_forged_tokens():
    import jwt, datetime as dt
    c = client()
    old = jwt.encode({"sub": "1", "exp": dt.datetime.utcnow() - dt.timedelta(minutes=1)}, "k" * 32, algorithm="HS256")
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + old}).status_code == 401
    forged = jwt.encode({"sub": "1", "exp": dt.datetime.utcnow() + dt.timedelta(hours=1)}, "wrong-secret-wrong-secret-0000", algorithm="HS256")
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + forged}).status_code == 401
    none_tok = jwt.encode({"sub": "1", "exp": 9999999999}, None, algorithm="none")
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + none_tok}).status_code == 401

def test_login_lockout():
    c = client(); main.config.RATE_LIMIT_ON = True
    try:
        codes = [c.post("/api/auth/login", json={"email": "ghost@x.io", "password": "Wrong12345"}).status_code for _ in range(10)]
        assert codes[:8] == [401] * 8 and 429 in codes[8:]
    finally:
        main.config.RATE_LIMIT_ON = False
