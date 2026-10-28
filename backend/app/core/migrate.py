"""Small, additive schema upgrades with a safety snapshot for existing SQLite databases."""
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, inspect, text

log = logging.getLogger(__name__)
MAX_SCHEMA_BACKUPS = 5

# table -> [(column, DDL fragment)]
NEW_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "sessions": [
        ("user_id", "VARCHAR(32) REFERENCES users(id) ON DELETE CASCADE"),
        ("focus_topics", "JSON"),
        ("practice_mode", "VARCHAR(20) NOT NULL DEFAULT 'live'"),
    ],
    "questions": [
        ("options_json", "JSON"),
        ("correct_answer", "VARCHAR(10)"),
        ("explanation", "TEXT"),
    ],
    "answers": [("voice_json", "JSON")],
    "user_llm_settings": [
        ("openai_model", "VARCHAR(100)"),
        ("openai_key_enc", "TEXT"),
        ("anthropic_model", "VARCHAR(100)"),
        ("anthropic_key_enc", "TEXT"),
        ("azure_model", "VARCHAR(100)"),
        ("azure_key_enc", "TEXT"),
        ("azure_endpoint", "VARCHAR(500)"),
        ("azure_api_version", "VARCHAR(40)"),
    ],
}
INDEXES = ["CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"]


def _pending_columns(engine: Engine) -> list[tuple[str, str, str]]:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    pending = []
    for table, columns in NEW_COLUMNS.items():
        if table not in tables:
            continue
        have = {column["name"] for column in insp.get_columns(table)}
        pending.extend((table, name, ddl) for name, ddl in columns if name not in have)
    return pending


def _backup_sqlite(engine: Engine) -> Path | None:
    """Create a consistent, bounded backup immediately before an existing schema is changed."""
    if engine.dialect.name != "sqlite" or not engine.url.database or engine.url.database == ":memory:":
        return None
    source = Path(engine.url.database)
    if not source.exists():
        return None
    backup_dir = source.parent / "schema-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"{source.stem}-before-upgrade-{stamp}{source.suffix or '.db'}"
    raw = engine.raw_connection()
    try:
        source_connection = raw.driver_connection
        with sqlite3.connect(destination) as target:
            source_connection.backup(target)
    finally:
        raw.close()
    backups = sorted(backup_dir.glob(f"{source.stem}-before-upgrade-*{source.suffix or '.db'}"))
    for old in backups[:-MAX_SCHEMA_BACKUPS]:
        old.unlink(missing_ok=True)
    log.warning("Created pre-upgrade database backup at %s", destination)
    return destination


def upgrade(engine: Engine) -> None:
    pending = _pending_columns(engine)
    if not pending:
        return
    _backup_sqlite(engine)
    tables = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for table, name, ddl in pending:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "sessions" in tables:
            for statement in INDEXES:
                conn.execute(text(statement))
