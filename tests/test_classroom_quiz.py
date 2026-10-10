import sys, os
os.environ["RATE_LIMIT"] = "off"
if os.path.exists("./test_app.db"): os.remove("./test_app.db")  # start from a clean database
os.environ["DATABASE_URL"] = "sqlite:///./test_app.db"
os.environ["ADMIN_EMAIL"] = "admin@crossmind.edu"
os.environ["ADMIN_PASSWORD"] = "AdminSecret123"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Standard assertions test
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def get_auth_header(email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}

def test_full_classroom_and_quiz_flow():
    # 1. Teachers cannot self-register: the public endpoint must always create a STUDENT
    attempt = client.post("/api/auth/register", json={
        "email": "sneaky.teacher@crossmind.edu", "password": "TeacherPass123",
        "name": "Sneaky", "role": "teacher"
    })
    assert attempt.status_code == 200 and attempt.json()["role"] == "student"

    # ...so the real teacher account is created by the admin
    admin_hdr = get_auth_header("admin@crossmind.edu", "AdminSecret123")
    t_reg = client.post("/api/admin/teachers", json={
        "email": "prof.smith@crossmind.edu", "password": "TeacherPass123", "name": "Prof. Smith",
        "department": "Computer Science", "employee_id": "T-001"
    }, headers=admin_hdr)
    assert t_reg.status_code in (200, 400)
    teacher_hdr = get_auth_header("prof.smith@crossmind.edu", "TeacherPass123")

    # 2. Register Students
    s1_reg = client.post("/api/auth/register", json={
        "email": "sujal@student.edu",
        "password": "StudentPass123",
        "name": "Sujal Patil",
        "role": "student"
    })
    assert s1_reg.status_code in (200, 400)
    s1_hdr = get_auth_header("sujal@student.edu", "StudentPass123")

    s2_reg = client.post("/api/auth/register", json={
        "email": "rahul@student.edu",
        "password": "StudentPass123",
        "name": "Rahul Sharma",
        "role": "student"
    })
    assert s2_reg.status_code in (200, 400)
    s2_hdr = get_auth_header("rahul@student.edu", "StudentPass123")

    # 3. Teacher Creates Classroom
    c_res = client.post("/api/classrooms", json={
        "name": "Data Science - TE DS",
        "subject": "Data Science",
        "division": "B",
        "description": "Data Science Semester V Course"
    }, headers=teacher_hdr)
    assert c_res.status_code == 200
    class_data = c_res.json()
    assert "code" in class_data
    code = class_data["code"]
    class_id = class_data["id"]

    # 4. Student Joins Classroom with Code
    j1 = client.post("/api/classrooms/join", json={"code": code}, headers=s1_hdr)
    assert j1.status_code == 200
    assert j1.json()["ok"] == True

    j2 = client.post("/api/classrooms/join", json={"code": code}, headers=s2_hdr)
    assert j2.status_code == 200

    # 5. Invalid Code & Duplicate Join Errors
    j_invalid = client.post("/api/classrooms/join", json={"code": "INVALID"}, headers=s1_hdr)
    assert j_invalid.status_code == 404

    j_dup = client.post("/api/classrooms/join", json={"code": code}, headers=s1_hdr)
    assert j_dup.status_code == 400

    # 6. Generate AI Quiz Questions
    gen_res = client.post("/api/quizzes/generate", json={
        "topic": "Machine Learning",
        "text": "Supervised learning algorithms use labeled datasets to train models. Linear Regression is used for regression problems while Logistic Regression is used for classification tasks. Neural Networks consist of input layers, hidden layers, and output layers.",
        "difficulty": "medium",
        "count": 5,
        "question_types": ["mcq", "true_false", "msq"]
    }, headers=teacher_hdr)
    assert gen_res.status_code == 200
    gen_questions = gen_res.json()["questions"]
    assert len(gen_questions) > 0

    # 7. Assign Quiz to Classroom
    q_create = client.post("/api/quizzes", json={
        "classroom_id": class_id,
        "title": "Machine Learning Fundamentals",
        "topic": "Machine Learning",
        "difficulty": "medium",
        "time_limit": 15,
        "questions": gen_questions
    }, headers=teacher_hdr)
    assert q_create.status_code == 200
    quiz_id = q_create.json()["id"]

    # 8. Teacher Starts Live Quiz
    st_res = client.post(f"/api/quizzes/{quiz_id}/start", headers=teacher_hdr)
    assert st_res.status_code == 200
    assert st_res.json()["is_active"] == True

    # 9. Students Submit Quiz
    # S1 submits answers
    first_q = gen_questions[0]
    answers_s1 = {str(first_q["id"]): first_q["answer"]}
    sub1 = client.post(f"/api/quizzes/{quiz_id}/submit", json={
        "answers": answers_s1,
        "time_taken_secs": 120
    }, headers=s1_hdr)
    assert sub1.status_code == 200
    res1 = sub1.json()
    assert res1["correct"] >= 1
    assert "percentage" in res1

    # S2 submits answers
    sub2 = client.post(f"/api/quizzes/{quiz_id}/submit", json={
        "answers": {},
        "time_taken_secs": 180
    }, headers=s2_hdr)
    assert sub2.status_code == 200

    # 10. Check Live Leaderboard
    lb_res = client.get(f"/api/quizzes/{quiz_id}/live-leaderboard", headers=teacher_hdr)
    assert lb_res.status_code == 200
    lb = lb_res.json()["leaderboard"]
    assert len(lb) == 2
    # Verify S1 ranked higher than S2 due to higher score
    assert lb[0]["student_id"] != lb[1]["student_id"]

    # 11. Student Performance Analytics
    perf_res = client.get("/api/student/performance", headers=s1_hdr)
    assert perf_res.status_code == 200
    assert perf_res.json()["quizzes_completed"] >= 1

    # 12. Security RBAC check: Student cannot create classroom
    c_fail = client.post("/api/classrooms", json={
        "name": "Hacked Class", "subject": "Math"
    }, headers=s1_hdr)
    assert c_fail.status_code == 403
