"""显式确认后事务性清空派生数据；导入本模块不会连接或修改数据库。"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url

from examdata.core.config import Settings

TABLES = (
    "question_asset",
    "official_answer",
    "generated_explanation",
    "mark_scheme_entry",
    "formula",
    "question_taxonomy",
    "difficulty",
    "question_similarity",
    "asset",
    "question",
    "mark_scheme",
    "paper",
    "validation_finding",
    "review_task",
    "parse_run",
)
DERIVED_SUBJECTS = (
    "question", "asset", "mark_scheme", "mark_scheme_entry", "official_answer",
    "generated_explanation", "paper", "formula", "difficulty", "question_taxonomy",
    "question_similarity",
)


def reset_derived(engine: Engine, *, confirm: bool = False) -> dict[str, int]:
    if engine.dialect.name != "sqlite":
        raise ValueError("Reset supports SQLite only")
    if not confirm:
        raise ValueError("Reset requires explicit confirmation")
    with engine.begin() as conn:
        protected_queries = (
            "SELECT COUNT(*) FROM field_override",
            "SELECT COUNT(*) FROM official_answer",
            "SELECT COUNT(*) FROM generated_explanation WHERE review_status != 'pending' OR is_official = 1 OR provider != 'rule-based'",
            "SELECT COUNT(*) FROM review_task WHERE status IN ('done', 'dismissed', 'in_progress') OR assignee IS NOT NULL OR resolution IS NOT NULL",
            "SELECT COUNT(*) FROM question_taxonomy WHERE source != 'auto' OR reviewed = 1",
            "SELECT COUNT(*) FROM difficulty WHERE source != 'estimated'",
            "SELECT COUNT(*) FROM formula WHERE source NOT IN ('embedded', 'ocr', 'llm', 'inline_text')",
        )
        if any(conn.scalar(text(query)) for query in protected_queries):
            raise ValueError("Reset refused: protected manual, reviewed, official data or overrides exist")
        counts = {}
        for table in TABLES:
            counts[table] = conn.execute(text(f"DELETE FROM {table}")).rowcount
        placeholders = ", ".join(f":subject_{i}" for i in range(len(DERIVED_SUBJECTS)))
        counts["provenance_edge"] = conn.execute(
            text(f"DELETE FROM provenance_edge WHERE subject_type IN ({placeholders})"),
            {f"subject_{i}": subject for i, subject in enumerate(DERIVED_SUBJECTS)},
        ).rowcount
        conn.execute(text(
            "UPDATE document_revision SET parse_status='pending', parse_error=NULL"
        ))
        conn.execute(text(
            "UPDATE document SET status='stored' WHERE current_revision_id IS NOT NULL"
        ))
        counts["pending_revisions"] = conn.scalar(text(
            "SELECT COUNT(*) FROM document_revision WHERE parse_status='pending'"
        ))
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="Override EXAMDATA_DATABASE_URL / Settings")
    parser.add_argument("--yes", action="store_true", help="Confirm deletion of all derived data")
    parser.add_argument("--dry-run", action="store_true", help="Only count rows; do not delete")
    args = parser.parse_args(argv)
    url = make_url(args.database_url or Settings().database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        path = Path(url.database).resolve()
        if not path.is_file():
            parser.error(f"Database does not exist: {path}")
        url = url.set(database=str(path))
    print(f"Target database: {url.render_as_string(hide_password=True)}")
    if not args.yes and not args.dry_run:
        parser.error("Refusing reset without --yes; use --dry-run to inspect first")
    engine = create_engine(url)
    if url.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
    try:
        if args.dry_run:
            with engine.connect() as conn:
                counts = {
                    table: conn.scalar(text(f"SELECT COUNT(*) FROM {table}"))
                    for table in TABLES
                }
            for table, count in counts.items():
                print(f"  would clear {table:<20} {count}")
        else:
            counts = reset_derived(engine, confirm=True)
            for table, count in counts.items():
                print(f"  {table:<20} {count}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
