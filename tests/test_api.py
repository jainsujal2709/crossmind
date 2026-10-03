import sys, os
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

    # Analyze document & generate crossword
    a = c.post("/api/documents/analyze", data={"topic": "machine learning"}, headers=student_hdr).json()
    assert "doc_id" in a

    p = c.post("/api/crosswords/generate", json={"doc_id": a["doc_id"], "difficulty": "easy", "count": 8}, headers=student_hdr).json()
    assert "id" in p
    assert "clues" in p
    assert "answer" not in p["clues"][0]

    # Submit crossword
    r = c.post(f"/api/crosswords/{p['id']}/submit", json={"answers": {}, "secs": 5}, headers=student_hdr).json()
    assert r["skipped"] == r["total"]
