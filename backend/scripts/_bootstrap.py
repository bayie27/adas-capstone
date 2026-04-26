from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def bootstrap_backend() -> Path:
    """Normalize cwd/sys.path so app imports and relative SQLite paths behave."""
    os.chdir(BACKEND_DIR)
    backend_dir_str = str(BACKEND_DIR)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)
    return BACKEND_DIR
