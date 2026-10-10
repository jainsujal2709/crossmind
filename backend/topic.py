"""Fetch real reference text for a topic from Wikipedia, so a topic-only request has real material to work from."""
import json, re, urllib.parse, urllib.request

API = "https://en.wikipedia.org/w/api.php"
UA = "CrossMind/1.0 (classroom learning platform; contact via site administrator)"
MAX_CHARS = 24000


class TopicError(Exception):
    pass


def _get(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(text):
    text = re.sub(r"^=+\s*(See also|References|External links|Further reading|Notes|Bibliography|Sources)\s*=+.*\Z", "", text, flags=re.S | re.M | re.I)
    text = re.sub(r"^=+.*?=+\s*$", "", text, flags=re.M)      # drop section headings
    text = re.sub(r"\[\d+\]|\[citation needed\]", "", text)    # footnote marks
    text = re.sub(r"\([^()]{0,80}\)", "", text)                # short parentheticals (dates, pronunciations)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()[:MAX_CHARS]


def fetch_topic_segments(topic):
    topic = (topic or "").strip()
    if len(topic) < 2:
        raise TopicError("Enter a topic of at least 2 characters.")
    try:
        hits = _get({"action": "query", "list": "search", "srsearch": topic, "srlimit": 3})["query"]["search"]
    except Exception:
        raise TopicError("Could not reach the reference source. Paste your notes or upload a file instead.")
    for h in hits:
        try:
            pages = _get({"action": "query", "prop": "extracts|pageprops", "explaintext": 1, "redirects": 1,
                          "ppprop": "disambiguation", "titles": h["title"]})["query"]["pages"]
        except Exception:
            raise TopicError("Could not reach the reference source. Paste your notes or upload a file instead.")
        page = pages[0] if pages else {}
        if page.get("missing") or "disambiguation" in (page.get("pageprops") or {}):
            continue
        text = _clean(page.get("extract") or "")
        if len(text.split()) >= 120:
            return [{"text": text, "source": f"Wikipedia: {page.get('title', h['title'])}"}]
    raise TopicError(f"Not enough reference material found for \u201c{topic}\u201d. Try a more specific topic, or paste your notes or upload a file.")
