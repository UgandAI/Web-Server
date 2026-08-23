import argparse
import logging
from pathlib import Path

from app.db.session import SessionLocal
from app.knowledge.ingestion import ingest_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Manually ingest a UTF-8 knowledge document")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source", required=True, help="Stable source identifier")
    parser.add_argument("--url")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    text = args.file.read_text(encoding="utf-8")
    with SessionLocal() as db:
        result = ingest_document(
            db, title=args.title, source_identifier=args.source, source_url=args.url, text=text
        )
        print(f"document_id={result.document.id} created={result.created} chunks={len(result.document.chunks)}")


if __name__ == "__main__":
    main()
