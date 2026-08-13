"""Build the RAG retrieval index from Documentation and BusinessTerm rows
already in Postgres (loaded by scripts/seed_database.py in Phase 3).

Re-running this script is safe: it clears document_chunks and rebuilds
it from scratch every time.

Usage:
    python scripts/ingest_documents.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config.database import SessionLocal, engine
from app.models import Base
from app.rag.retrieval import clear_chunks, ingest_business_terms, ingest_documentation


def main() -> None:
    print("Ensuring document_chunks table exists...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        print("Clearing existing chunks...")
        clear_chunks(session)

        print("Chunking + embedding documentation...")
        doc_count = ingest_documentation(session)

        print("Chunking + embedding business terms...")
        term_count = ingest_business_terms(session)

        session.commit()
        print(f"Done. {doc_count} documentation chunks, {term_count} business-term chunks.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
