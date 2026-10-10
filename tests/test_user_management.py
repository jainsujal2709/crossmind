import sys, os
os.environ["RATE_LIMIT"] = "off"
if os.path.exists("./test_users.db"): os.remove("./test_users.db")  # start from a clean database
os.environ["DATABASE_URL"] = "sqlite:///./test_users.db"
os.environ["ADMIN_EMAIL"] = "boss@crossmind.edu"
os.environ["ADMIN_PASSWORD"] = "BossPass123"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def hdr(e, p):
    r = c.post("/api/auth/login", json={"email": e, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}

def test_user_management():
    admin = hdr("boss@crossmind.edu", "BossPass123")

    # --- student self-registration works and is stored with profile data
    r = c.post("/api/auth/register", json={"email": "Stu@x.io", "password": "secret123", "name": "Stu <b>X</b>",
                                           "roll_no": "R1", "course": "BCA", "division": "A", "role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "student"      # 'role' ignored
    assert c.post("/api/auth/register", json={"email": "weak@x.io", "password": "short1", "name": "W"}).status_code == 422       # too short
    assert c.post("/api/auth/register", json={"email": "weak@x.io", "password": "onlyletters", "name": "W"}).status_code == 422  # no number
    assert c.post("/api/auth/register", json={"email": "stu@x.io", "password": "secret123", "name": "dup"}).status_code == 400
    stu = hdr("stu@x.io", "secret123")                                    # email is case-insensitive

    students = c.get("/api/admin/users?role=student", headers=admin).json()
    me = next(u for u in students if u["email"] == "stu@x.io")
    assert me["roll_no"] == "R1" and me["course"] == "BCA" and me["last_login"] != "Never"

    # --- teacher cannot be created by the public or by a student
    assert c.post("/api/admin/teachers", json={"name": "T", "email": "t@x.io", "password": "secret123"}, headers=stu).status_code == 403

    # --- admin creates / edits teacher
    t = c.post("/api/admin/teachers", json={"name": "Teach", "email": "t@x.io", "password": "secret123",
                                            "department": "Math", "employee_id": "E9"}, headers=admin)
    assert t.status_code == 200 and t.json()["role"] == "teacher"
    tid = t.json()["id"]
    assert c.post("/api/admin/teachers", json={"name": "T2", "email": "t@x.io", "password": "secret123"}, headers=admin).status_code == 400

    u = c.put(f"/api/admin/users/{tid}", json={"name": "Teach Two", "department": "Physics", "password": "newpass123"}, headers=admin)
    assert u.status_code == 200 and u.json()["department"] == "Physics"
    hdr("t@x.io", "newpass123")                                           # reset password works
    assert c.post("/api/auth/login", json={"email": "t@x.io", "password": "secret123"}).status_code == 401

    # --- search / filter
    assert [x["email"] for x in c.get("/api/admin/users?role=teacher&q=physics", headers=admin).json()] == ["t@x.io"]

    # --- disable blocks login
    c.put(f"/api/admin/users/{tid}", json={"active": False}, headers=admin)
    assert c.post("/api/auth/login", json={"email": "t@x.io", "password": "newpass123"}).status_code == 403
    c.put(f"/api/admin/users/{tid}", json={"active": True}, headers=admin)

    # --- teacher data + delete teacher cascades cleanly (previously a FK error)
    th = hdr("t@x.io", "newpass123")
    cls = c.post("/api/classrooms", json={"name": "Cls", "subject": "Maths"}, headers=th).json()
    assert c.post("/api/classrooms/join", json={"code": cls["code"]}, headers=stu).status_code == 200
    assert c.post("/api/classrooms/join", json={"code": cls["code"]}, headers=th).status_code == 403   # teachers can't join
    assert c.delete(f"/api/admin/users/{tid}", headers=admin).status_code == 200
    assert c.get(f"/api/classrooms/{cls['id']}", headers=stu).status_code == 404

    # --- admin accounts are protected; CSV export / import
    aid = c.get("/api/auth/me", headers=admin).json()["id"]
    assert c.delete(f"/api/admin/users/{aid}", headers=admin).status_code == 400
    csv_text = "name,email,password,department\nA Teacher,a1@x.io,pass1234,CS\nbad,notanemail,x,\n"
    r = c.post("/api/admin/import", data={"role": "teacher"}, files={"file": ("t.csv", csv_text)}, headers=admin).json()
    assert r["created"] == 1 and len(r["skipped"]) == 1
    exp = c.get("/api/admin/export?role=teacher", headers=admin)
    assert exp.status_code == 200 and "a1@x.io" in exp.text and "pw" not in exp.text.lower().split("\n")[0]
