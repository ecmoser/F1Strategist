import sys
from pathlib import Path

# Ensure project root is on sys.path so tests can import `lib` when pytest is
# invoked from different working directories or CI runners.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
