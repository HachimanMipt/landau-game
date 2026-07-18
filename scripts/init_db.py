from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.database import init_database


def main() -> None:
    init_database()
    settings = get_settings()
    print(f"Database initialized at {settings.database_url}")


if __name__ == "__main__":
    main()

