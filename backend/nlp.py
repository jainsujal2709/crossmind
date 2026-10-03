import re, math
from collections import Counter
STOP = set("""this that with from have been were will would could should about which their there these those into than then them they what when where while other such also only more most many much some very just like over under between within without because through during before after being does done make made using used uses based each every both however therefore thus often usually example method system systems thing things data information process""".split())
def sentences(segs):
    for s in segs:
        for t in re.split(r"(?<=[.!?])\s+|\n+", re.sub(r"[ \t]+", " ", s["text"])):
            if len(t.split()) >= 5: yield t.strip(), s["source"]
def concepts(segs, top=60):
    sents = list(sentences(segs)); tf, df, seen = Counter(), Counter(), {}
    for t, src in sents:
        ws = set()
        for w in re.findall(r"[A-Za-z]{5,15}", t):
            if w.lower() in STOP: continue
            u = w.upper(); tf[u] += 1; ws.add(u)
            if re.search(rf"\b{w}\b\s+(is|are|refers to|means|describes)\b", t, re.I): tf[u] += 2
        for u in ws: df[u] += 1
    n = len(sents) + 1
    ranked = sorted(tf, key=lambda w: tf[w] * math.log(1 + n / df[w]) , reverse=True)[:top]
    return [{"term": w, "importance": "High" if i < top // 3 else "Medium" if i < 2 * top // 3 else "Low"} for i, w in enumerate(ranked)]
def _mask(s, term): return re.sub(rf"\b{term}\w*", "_____", s, flags=re.I)
def build_items(segs, difficulty, selected=None, limit=40):
    sents = list(sentences(segs)); items, used = [], set()
    for c in (selected or [x["term"] for x in concepts(segs)]):
        if c in used: continue
        cand = [(t, s) for t, s in sents if re.search(rf"\b{c}\b", t, re.I)]
        if not cand: continue
        cand.sort(key=lambda x: (not re.search(rf"\b{c}\b\s+(is|are|refers to|means)", x[0], re.I), abs(len(x[0]) - 110)))
        t, src = cand[0]; m = _mask(t, c)
        pred = re.split(r"\b(?:is|are|refers to|means|describes)\b", m, maxsplit=1)
        if difficulty == "easy": clue = m + f" ({len(c)})"
        elif difficulty == "medium": clue = ("Concept: " + pred[1].strip(" .") if len(pred) > 1 and len(pred[1].split()) > 3 else m) + f" ({len(c)})"
        else:
            body = pred[1] if len(pred) > 1 else m
            clue = "Term implied by: " + re.split(r",|;", body.strip(" ."))[0].strip()
        if re.search(rf"\b{c}", clue, re.I) or len(clue.split()) < 4: continue  # validation: never leak answer
        used.add(c); items.append({"answer": c, "clue": clue[0].upper() + clue[1:], "explanation": t, "source": src})
        if len(items) >= limit: break
    return items
