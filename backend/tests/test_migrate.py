from sqlalchemy import create_engine, inspect, text

from app.core import migrate


def test_file_database_is_backed_up_before_additive_upgrade(tmp_path):
    database = tmp_path / "app.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE sessions (id VARCHAR(32) PRIMARY KEY, title VARCHAR(200))"))
        connection.execute(text("INSERT INTO sessions (id, title) VALUES ('legacy', 'Existing interview')"))

    migrate.upgrade(engine)

    backups = list((tmp_path / "schema-backups").glob("app-before-upgrade-*.db"))
    assert len(backups) == 1
    backup_engine = create_engine(f"sqlite:///{backups[0]}")
    with backup_engine.connect() as connection:
        assert connection.execute(text("SELECT title FROM sessions WHERE id='legacy'")).scalar_one() == "Existing interview"
    assert "practice_mode" in {column["name"] for column in inspect(engine).get_columns("sessions")}


def test_upgrade_is_idempotent_and_does_not_create_extra_backup(tmp_path):
    database = tmp_path / "app.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(32) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE sessions (id VARCHAR(32) PRIMARY KEY, title VARCHAR(200))"))

    migrate.upgrade(engine)
    migrate.upgrade(engine)

    assert len(list((tmp_path / "schema-backups").glob("*.db"))) == 1
