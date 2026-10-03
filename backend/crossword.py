import random
def _fits(g, o, w, r, c, d):
    dr, dc = (0, 1) if d == 0 else (1, 0)
    if (r - dr, c - dc) in g or (r + dr * len(w), c + dc * len(w)) in g: return -1
    x = 0
    for i, ch in enumerate(w):
        p = (r + dr * i, c + dc * i)
        if p in g:
            if g[p] != ch or d in o[p]: return -1
            x += 1
        elif (p[0] + dc, p[1] + dr) in g or (p[0] - dc, p[1] - dr) in g: return -1
    return x
def _attempt(words):
    g, o, pl = {}, {}, []
    def put(w, r, c, d):
        dr, dc = (0, 1) if d == 0 else (1, 0)
        for i, ch in enumerate(w):
            p = (r + dr * i, c + dc * i); g[p] = ch; o.setdefault(p, set()).add(d)
        pl.append({"answer": w, "row": r, "col": c, "dir": "across" if d == 0 else "down"})
    put(words[0], 0, 0, 0)
    for w in words[1:]:
        best = None
        for i, ch in enumerate(w):
            for (pr, pc), l in list(g.items()):
                if l != ch: continue
                for d in (0, 1):
                    r, c = (pr, pc - i) if d == 0 else (pr - i, pc)
                    if _fits(g, o, w, r, c, d) >= 1:
                        rs = [p[0] for p in g] + [r, r + (len(w) if d else 0)]; cs = [p[1] for p in g] + [c, c + (len(w) if not d else 0)]
                        a = (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1)
                        if not best or a < best[0]: best = (a, r, c, d)
        if best: put(w, best[1], best[2], best[3])
    mr, mc = min(p["row"] for p in pl), min(p["col"] for p in pl)
    for p in pl: p["row"] -= mr; p["col"] -= mc
    return pl
def number(pl):
    starts = sorted({(p["row"], p["col"]) for p in pl}); nums = {s: i + 1 for i, s in enumerate(starts)}
    for p in pl: p["n"] = nums[(p["row"], p["col"])]; p["len"] = len(p["answer"])
    return sorted(pl, key=lambda p: (p["dir"] != "across", p["n"]))
def validate(pl):
    g = {}; seen = set()
    for p in pl:
        if p["answer"] in seen: return False
        seen.add(p["answer"])
        for i, ch in enumerate(p["answer"]):
            k = (p["row"] + (i if p["dir"] == "down" else 0), p["col"] + (i if p["dir"] == "across" else 0))
            if g.setdefault(k, ch) != ch: return False
    return True
def size(pl): return [max(p["row"] + (p["len"] if p["dir"] == "down" else 1) for p in pl), max(p["col"] + (p["len"] if p["dir"] == "across" else 1) for p in pl)]
def generate(answers, count, tries=40):
    answers = list(dict.fromkeys(a for a in answers if 3 <= len(a) <= 15)); best = []
    for t in range(tries):
        order = sorted(answers, key=lambda a: (-len(a), random.random())) if t == 0 else random.sample(answers, len(answers))
        if t: order.sort(key=lambda a: -len(a) if random.random() < .5 else 0)
        pl = _attempt(order)[:] if order else []
        if len(pl) > len(best) and validate(pl): best = pl
        if len(best) >= count: break
    best = best[:count] if len(best) > count else best
    return number(best) if validate(best) else []
