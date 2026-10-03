import shutil, os
from pathlib import Path

def build():
    dist = Path("dist")
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree("public", dist)

    url = os.environ.get("BACKEND_URL", "").rstrip("/")

    for p in dist.rglob("*.js"):
        s = p.read_text(encoding="utf-8")
        s = s.replace("__BACKEND_URL__", url)
        p.write_text(s, encoding="utf-8")

    print(f"Dist build complete! Output in dist/ (BACKEND_URL: '{url or 'relative'}')")

if __name__ == "__main__":
    build()
