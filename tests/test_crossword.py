import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import crossword, nlp
def test_generate_valid():
    pl = crossword.generate(["SUPERVISED", "REGRESSION", "CLUSTERING", "OVERFITTING", "GRADIENT", "NETWORK", "VALIDATION"], 7)
    assert len(pl) >= 3 and crossword.validate(pl) and all("n" in p for p in pl)
def test_nlp_no_leak():
    segs = [{"text": open(os.path.join(os.path.dirname(__file__), "..", "data", "sample_data", "machine_learning.txt")).read(), "source": "t"}]
    items = nlp.build_items(segs, "hard")
    assert items and all(i["answer"].lower() not in i["clue"].lower() for i in items)
