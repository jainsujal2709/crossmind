import sys, os
os.environ["RATE_LIMIT"] = "off"
if os.path.exists("./test.db"): os.remove("./test.db")  # start from a clean database
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ADMIN_EMAIL"] = "a@x.io"
os.environ["ADMIN_PASSWORD"] = "AdminPass123"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def get_token(e, p):
    res = c.post("/api/auth/login", json={"email": e, "password": p})
    assert res.status_code == 200, f"Login failed for {e}: {res.text}"
    return {"Authorization": "Bearer " + res.json()["token"]}

def test_flow():
    # Register Admin & Student
    c.post("/api/auth/register", json={"email": "a@x.io", "password": "AdminPass123", "name": "Admin User", "role": "admin"})
    c.post("/api/auth/register", json={"email": "u@x.io", "password": "password1", "name": "U", "role": "student"})

    student_hdr = get_token("u@x.io", "password1")
    admin_hdr = get_token("a@x.io", "AdminPass123")

    # Student cannot access admin users endpoint
    assert c.get("/api/admin/users", headers=student_hdr).status_code == 403

    # Admin can access admin users endpoint
    assert c.get("/api/admin/users", headers=admin_hdr).status_code == 200

    # Students can NOT upload documents or use crosswords (teachers/admin only)
    assert c.post("/api/documents/analyze", data={"topic": "machine learning"}, headers=student_hdr).status_code == 403
    assert c.post("/api/crosswords/generate", json={"doc_id": 1, "difficulty": "easy", "count": 8}, headers=student_hdr).status_code == 403
    assert c.get("/api/crosswords", headers=student_hdr).status_code == 403

    # A teacher (created by the admin) can analyze a document & generate a crossword
    c.post("/api/admin/teachers", json={"email": "t@x.io", "password": "teachpass1", "name": "T"}, headers=admin_hdr)
    teacher_hdr = get_token("t@x.io", "teachpass1")
    import os
    notes = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sample_data", "machine_learning.txt"), encoding="utf-8").read()
    a = c.post("/api/documents/analyze", data={"topic": "machine learning", "text": notes}, headers=teacher_hdr).json()
    assert "doc_id" in a

    p = c.post("/api/crosswords/generate", json={"doc_id": a["doc_id"], "difficulty": "easy", "count": 8}, headers=teacher_hdr).json()
    assert "id" in p
    assert "clues" in p
    assert "answer" not in p["clues"][0]

    # Submit crossword
    r = c.post(f"/api/crosswords/{p['id']}/submit", json={"answers": {}, "secs": 5}, headers=teacher_hdr).json()
    assert r["skipped"] == r["total"]

    # Student performance endpoint works with no quizzes taken (real data, not placeholders)
    perf = c.get("/api/student/performance", headers=student_hdr).json()
    assert perf["quizzes_completed"] == 0 and perf["strong_topics"] == [] and perf["classrooms_joined"] == 0
