#!/usr/bin/env python3
"""Apply Private Investment OS migrations with an optional backup and receipt."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS = APP / "data" / "migrations"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sql_statements(sql: str):
    """Yield complete SQLite statements without splitting trigger bodies."""
    pending = ""
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            pending = ""
            if statement:
                yield statement
    if pending.strip():
        raise RuntimeError("INCOMPLETE_MIGRATION_SQL")


def migrate(db_path: Path, migrations_dir: Path = DEFAULT_MIGRATIONS, backup_path: Path | None = None) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    existed = db_path.exists()
    if existed and backup_path:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.resolve() == backup_path.resolve():
            raise ValueError("BACKUP_PATH_MUST_DIFFER_FROM_DATABASE")
        # SQLite's online backup API takes a transactionally consistent snapshot,
        # including committed pages that are still resident in an active WAL.
        with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as target:
            source.backup(target)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations(
          version TEXT PRIMARY KEY,
          filename TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          applied_at TEXT NOT NULL
        )
    """)
    conn.commit()
    applied, skipped = [], []
    try:
        for migration in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
            version = migration.name.split("_", 1)[0]
            sql = migration.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode()).hexdigest()
            row = conn.execute("SELECT sha256 FROM schema_migrations WHERE version=?", (version,)).fetchone()
            if row:
                if row[0] != digest:
                    raise RuntimeError(f"MIGRATION_CHECKSUM_MISMATCH:{version}")
                skipped.append(version)
                continue
            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in sql_statements(sql):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations(version,filename,sha256,applied_at) VALUES(?,?,?,?)",
                    (version, migration.name, digest, utc_now()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied.append(version)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        conn.close()
    return {
        "db": str(db_path),
        "databaseExisted": existed,
        "backup": str(backup_path) if backup_path else None,
        "applied": applied,
        "skipped": skipped,
        "schemaVersion": versions[-1] if versions else None,
        "integrityCheck": integrity,
        "foreignKeyViolations": len(foreign_keys),
        "completedAt": utc_now(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--migrations-dir", type=Path, default=DEFAULT_MIGRATIONS)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = migrate(args.db, args.migrations_dir, args.backup)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
