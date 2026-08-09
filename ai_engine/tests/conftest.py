"""ai_engine/ is not a package — its modules use flat `from config import ...`
imports that assume ai_engine/ is on sys.path directly (mirroring what
backend/scripts/_bootstrap.py does for the backend). Put it there before any
test module tries to `import config`, `import events`, etc.
"""

import sys
from pathlib import Path

AI_ENGINE_DIR = Path(__file__).resolve().parents[1]

if str(AI_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_ENGINE_DIR))
