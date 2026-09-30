"""Scheduled ingestion sweep.

Replaces the manual `python -m app.knowledge.ingest` workflow with an unattended job that
scans `KNOWLEDGE_INGESTION_DIR` for new `.txt` sources and ingests them. Two entry points
are provided for the two ways this gets scheduled:

- `main()` / `python -m app.knowledge.worker` — a plain cron job on a long-running host.
- `lambda_handler(event, context)` — an AWS Lambda function invoked by a CloudWatch Events
  (EventBridge) scheduled rule. Deploy the checked-out `app` package as the Lambda's code,
  set `app.knowledge.worker.lambda_handler` as the handler, and attach an EventBridge rule
  with a `rate(...)` or `cron(...)` schedule expression that targets the function. This
  module does not create AWS resources itself.

Every sweep is logged to `ingestion_runs` (see `app/models/knowledge.py::IngestionRun`) so
runs are inspectable via `GET /knowledge/ingestion-runs`.
"""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.knowledge.ingestion import ingest_document
from app.models.knowledge import IngestionRun
from app.models.user import utc_now

logger = logging.getLogger(__name__)


def _iter_source_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.txt") if path.is_file())


def run_ingestion_sweep(db: Session, *, directory: Path | None = None, embedding_service=None) -> IngestionRun:
    """Ingest every `.txt` file in `directory` and record the outcome as an IngestionRun."""
    source_dir = directory if directory is not None else Path(settings.KNOWLEDGE_INGESTION_DIR)
    run = IngestionRun(source_directory=str(source_dir), status="running")
    db.add(run)
    db.flush()

    files = _iter_source_files(source_dir)
    run.files_scanned = len(files)
    errors: list[str] = []
    for path in files:
        try:
            with db.begin_nested():
                text = path.read_text(encoding="utf-8")
                result = ingest_document(
                    db,
                    title=path.stem.replace("_", " ").replace("-", " ").title(),
                    source_identifier=f"file:{path.name}",
                    text=text,
                    embedding_service=embedding_service,
                    commit=False,
                )
            if result.created:
                run.documents_created += 1
                run.chunks_created += len(result.document.chunks)
            else:
                run.documents_skipped += 1
        except Exception as exc:
            logger.warning("Failed to ingest %s: %s", path, exc)
            errors.append(f"{path.name}: {exc}")

    run.status = "success" if not errors else "completed_with_errors"
    run.error_message = "; ".join(errors)[:2000] or None
    run.finished_at = utc_now()
    db.commit()
    db.refresh(run)
    return run


def lambda_handler(event, context):
    """AWS Lambda entry point for a CloudWatch/EventBridge scheduled rule."""
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        run = run_ingestion_sweep(db)
    return {
        "status": run.status,
        "files_scanned": run.files_scanned,
        "documents_created": run.documents_created,
        "documents_skipped": run.documents_skipped,
        "chunks_created": run.chunks_created,
        "error_message": run.error_message,
    }


def main() -> None:
    """CLI entry point for cron: `python -m app.knowledge.worker`."""
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        run = run_ingestion_sweep(db)
    print(
        f"status={run.status} files_scanned={run.files_scanned} "
        f"documents_created={run.documents_created} documents_skipped={run.documents_skipped} "
        f"chunks_created={run.chunks_created}"
    )


if __name__ == "__main__":
    main()
