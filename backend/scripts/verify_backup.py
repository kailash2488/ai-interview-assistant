"""Read-only integrity and row-count check for a SQLite schema backup."""
import argparse
import sqlite3
from pathlib import Path


def verify(path: Path) -> dict[str, int]:
    if not path.is_file() or path.suffix not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Choose an existing SQLite backup file")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError(f"Backup integrity check failed: {integrity}")
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        counts = {}
        for table in tables:
            quoted = table.replace('"', '""')
            counts[table] = connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
        return counts
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    counts = verify(args.backup)
    print("Backup integrity: ok")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()
