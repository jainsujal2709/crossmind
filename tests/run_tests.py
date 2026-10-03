import sys, os
sys.path.insert(0, os.path.dirname(__file__))

print("Running CrossMind Test Suite...")
from test_classroom_quiz import test_full_classroom_and_quiz_flow
from test_api import test_flow

try:
    test_full_classroom_and_quiz_flow()
    print("[SUCCESS] Classroom & Quiz Flow Test Passed!")
    test_flow()
    print("[SUCCESS] General API & Crossword Flow Test Passed!")
    print("\nALL TESTS PASSED SUCCESSFULLY!")
except Exception as e:
    print(f"\n[FAILURE] Test Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
