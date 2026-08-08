from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def bootstrap_backend() -> Path:
    """Put backend/ on sys.path so scripts can `from app.core...` regardless of CWD.

    DATABASE_URL is anchored to REPO_ROOT by Settings itself, so this no longer
    needs to chdir into BACKEND_DIR to make relative SQLite paths resolve.
    """
    backend_dir_str = str(BACKEND_DIR)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)
    return BACKEND_DIR
