"""Teacher uploads (PDF etc.) -> analyze -> quiz generation, including the messy real-world cases."""
import sys, os
if os.path.exists("./test_uploads.db"): os.remove("./test_uploads.db")  # start from a clean database
os.environ["DATABASE_URL"] = "sqlite:///./test_uploads.db"
os.environ["ADMIN_EMAIL"] = "a@x.io"
os.environ["ADMIN_PASSWORD"] = "AdminPass123"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    import pymupdf as fitz
except ImportError:
    import fitz
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def hdr(e, p):
    r = c.post("/api/auth/login", json={"email": e, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}

def make_pdf(pages):
    d = fitz.open()
    for text in pages:
        d.new_page().insert_textbox(fitz.Rect(50, 50, 545, 790), text, fontsize=11)
    return d.tobytes()

def upload(h, data, name="notes.pdf"):
    return c.post("/api/documents/analyze", files=[("files", (name, data, "application/pdf"))],
                  data={"text": "", "topic": ""}, headers=h)

def test_pdf_to_quiz():
    admin = hdr("a@x.io", "AdminPass123")
    c.post("/api/admin/teachers", json={"name": "T", "email": "t@x.io", "password": "teachpass1"}, headers=admin)
    c.post("/api/auth/register", json={"name": "S", "email": "s@x.io", "password": "studpass1"})
    th, st = hdr("t@x.io", "teachpass1"), hdr("s@x.io", "studpass1")

    # 0) Text clean-up used for every PDF page: ligatures and hyphenated line breaks are repaired
    import parser as _p
    assert _p.clean_text("The \ufb01rewall of a ne-\ntwork") == "The firewall of a network"

    # 1) Normal paragraphs with hyphenated line breaks -> words are repaired
    para = ("A computer ne-\\ntwork is a collection of interconnected devices that share re-\\nsources and exchange data. "
            "The firewall is a security system that monitors and controls incoming traffic.\\n\\n"
            "Routing is the process of selecting a path for packets across networks. "
            "A protocol is a set of rules that governs communication between devices.\\n").replace("\\n", "\n")
    r = upload(th, make_pdf([para * 3]))
    assert r.status_code == 200, r.text
    terms = [x["term"] for x in r.json()["concepts"]]
    assert "NETWORK" in terms and "FIREWALL" in terms
    g = c.post("/api/quizzes/generate", json={"doc_id": r.json()["doc_id"], "topic": "Networks", "count": 10}, headers=th)
    assert g.status_code == 200 and g.json()["count"] >= 3

    # 2) REGRESSION: lecture slides repeat the same bullets on every page. This used to crash with a 500.
    bullets = ["TCP is a reliable transport protocol", "UDP is connectionless and very fast",
               "A router forwards packets between networks", "A firewall filters network traffic",
               "DNS translates domain names into addresses", "A switch connects devices inside a LAN"]
    slide = "\n".join("\u2022 " + b for b in bullets)
    r = upload(th, make_pdf([slide] * 6))
    assert r.status_code == 200, r.text
    g = c.post("/api/quizzes/generate", json={"doc_id": r.json()["doc_id"], "topic": "Slides", "count": 15}, headers=th)
    assert g.status_code == 200, g.text
    assert 3 <= g.json()["count"] <= len(bullets)          # one question per unique sentence, no crash

    # 3) Scanned / image-only PDF -> clear message instead of a vague error
    img = fitz.open(); img.new_page().draw_rect(fitz.Rect(50, 50, 300, 300), fill=(0, 0, 0))
    r = upload(th, img.tobytes())
    assert r.status_code == 422 and "scanned" in r.json()["detail"].lower()

    # 4) Students cannot upload material or generate quizzes
    assert upload(st, make_pdf([para])).status_code == 403
    assert c.post("/api/quizzes/generate", json={"topic": "x"}, headers=st).status_code == 403
