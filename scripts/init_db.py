"""Create all tables defined in app.models against DATABASE_URL.

This prototype uses create_all() instead of migrations (Alembic) — the
schema is small and still moving fast; a migration tool is a reasonable
future improvement once the schema stabilizes, not something this project
needs yet.

Usage:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config.database import engine
from app.models import Base


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print(f"Created tables: {', '.join(sorted(Base.metadata.tables))}")


if __name__ == "__main__":
    main()
