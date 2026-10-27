"""Tiny schema upgrades for databases created before a column existed (create_all only makes missing tables)."""
from sqlalchemy import Engine, inspect, text


def upgrade(engine: Engine) -> None:
    insp = inspect(engine)
    if "sessions" in insp.get_table_names() and "user_id" not in {c["name"] for c in insp.get_columns("sessions")}:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR(32) REFERENCES users(id) ON DELETE CASCADE"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"))
