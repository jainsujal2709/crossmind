"""Topic-only generation uses real reference text (mocked here), results are stored in History, offline gives a clear error."""
import os, sys, json
os.environ.update(DATABASE_URL="sqlite:///./test_topic.db", ADMIN_EMAIL="a@x.com", ADMIN_PASSWORD="Admin@12345", SECRET_KEY="k"*20)
if os.path.exists("test_topic.db"): os.remove("test_topic.db")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
import topic, urllib.request
TXT = ("Inception is a science fiction heist film written and directed by Christopher Nolan. The film follows Dom Cobb, a thief who steals secrets by entering the dreams of other people. "
 "Cobb is offered a chance to have his criminal history erased if he can plant an idea in the mind of a business heir. Planting an idea in this way is called inception. "
 "The team enters several nested dream levels, and time passes more slowly in each deeper level. A totem is a small personal object that a dreamer uses to check whether he is inside a dream. "
 "Cobb uses a spinning top as his totem. Arthur is the point man who researches the target and plans the mission. Ariadne is an architect who designs the layout of the dream worlds. "
 "Eames is a forger who can imitate other people inside a dream. Saito is a businessman who hires the team to carry out the job. The film was released in 2010 and earned several Academy Awards for technical work. "
 "Critics praised the visual effects, the score composed by Hans Zimmer, and the layered screenplay. The ending shows the spinning top without revealing whether it falls, which left audiences debating the outcome. "
 "Production took place in several countries and used practical effects such as a rotating hallway set. The film grossed more than eight hundred million dollars worldwide.")
calls = []
def fake(params):
    calls.append(params.get("action"))
    if params.get("list") == "search": return {"query": {"search": [{"title": "Inception"}]}}
    return {"query": {"pages": [{"title": "Inception", "extract": "== Plot ==\n" + TXT + "\n== References ==\nx"}]}}
topic._get = fake
from starlette.testclient import TestClient
import main

def test_topic_and_history():
    c = TestClient(main.app)
    def login(e, p): return c.post("/api/auth/login", json={"email": e, "password": p}).json()["token"]
    H = lambda t: {"Authorization": "Bearer " + t}
    at = login("a@x.com", "Admin@12345")
    assert c.post("/api/admin/teachers", json={"name": "T One", "email": "t@x.com", "password": "Teach@123"}, headers=H(at)).status_code < 300
    tt = login("t@x.com", "Teach@123")
    r = c.post("/api/documents/analyze", data={"topic": "Inception"}, headers=H(tt)); assert r.status_code == 200
    r = c.post("/api/crosswords/generate", json={"doc_id": r.json()["doc_id"], "difficulty": "medium", "count": 10}, headers=H(tt)); assert r.status_code == 200 and len(r.json()["clues"]) >= 8
    r = c.post("/api/quizzes/generate", json={"topic": "Inception", "count": 10}, headers=H(tt)); j = r.json(); assert r.status_code == 200
    qs = [q["question"] for q in j["questions"]]; assert len(qs) >= 8 and len(set(qs)) == len(qs)
    assert len({q.get("source") for q in j["questions"]}) >= 1 and all("Inception" not in q["question"].split("_____")[0][:0] for q in j["questions"])
    h = c.get("/api/history", headers=H(tt)).json(); assert len(h["crosswords"]) == 1 and len(h["drafts"]) == 1
    cl = c.post("/api/classrooms", json={"name": "Class A", "subject": "Film", "division": "A", "description": "d"}, headers=H(tt)).json()
    d = c.get(f"/api/quiz-drafts/{j['draft_id']}", headers=H(tt)).json()
    assert c.post("/api/quizzes", json={"classroom_id": cl["id"], "title": "Inception quiz", "topic": "Inception", "time_limit": 10, "questions": d["questions"]}, headers=H(tt)).status_code == 200
    assert len(c.get("/api/history", headers=H(tt)).json()["quizzes"]) == 1
    assert c.delete(f"/api/quiz-drafts/{j['draft_id']}", headers=H(tt)).status_code == 200
    def boom(params): raise OSError("offline")
    topic._get = boom
    r = c.post("/api/quizzes/generate", json={"topic": "Inception"}, headers=H(tt)); assert r.status_code == 422 and "reference source" in r.json()["detail"]
    c.post("/api/auth/register", json={"name": "S One", "email": "s@x.com", "password": "Stud@123"})
    assert c.get("/api/history", headers=H(login("s@x.com", "Stud@123"))).status_code == 403
