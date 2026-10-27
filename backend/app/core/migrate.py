"""Tiny schema upgrades for databases created before a column existed (create_all only makes missing tables)."""
from sqlalchemy import Engine, inspect, text

# table -> [(column, DDL fragment)]
NEW_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "sessions": [
        ("user_id", "VARCHAR(32) REFERENCES users(id) ON DELETE CASCADE"),
        ("focus_topics", "JSON"),
    ],
    "answers": [("voice_json", "JSON")],
}
INDEXES = ["CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"]


def upgrade(engine: Engine) -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, columns in NEW_COLUMNS.items():
            if table not in tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in columns:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if "sessions" in tables:
            for statement in INDEXES:
                conn.execute(text(statement))
