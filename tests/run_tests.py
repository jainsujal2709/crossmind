"""Runs every test file in its own process (each file configures its own database/admin via env vars)."""
import sys, os, subprocess

here = os.path.dirname(os.path.abspath(__file__))
print("Running CrossMind Test Suite...")
failed = False
for f in ("test_crossword.py", "test_classroom_quiz.py", "test_api.py", "test_user_management.py"):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", os.path.join(here, f)], cwd=os.path.join(here, ".."))
    print(("[SUCCESS] " if r.returncode == 0 else "[FAILURE] ") + f)
    failed |= r.returncode != 0
print("\nALL TESTS PASSED SUCCESSFULLY!" if not failed else "\nSOME TESTS FAILED")
sys.exit(1 if failed else 0)
