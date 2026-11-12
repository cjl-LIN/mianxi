from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

JSON_FIELDS = ("aliases", "tags", "sources", "keywords", "questions", "match_terms")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    override = os.environ.get("DATA_DIR")
    return Path(override) if override else repo_root() / "data"


def db_path() -> Path:
    override = os.environ.get("APP_DB_PATH")
    return Path(override) if override else data_dir() / "app.db"


def vault_path() -> Path:
    override = os.environ.get("VAULT_PATH")
    return Path(override) if override else data_dir() / "vault"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with db() as conn:
        conn.executescript(schema)
        conn.execute("INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '1')")


def loads(value, default):
    if value is None or value == "":
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return default if parsed is None else parsed


def hydrate_kp(row) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in JSON_FIELDS:
        if key in data:
            data[key] = loads(data[key], [])
    if "fallback" in data:
        data["fallback"] = bool(data["fallback"])
    return data


def one(conn, sql: str, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def many(conn, sql: str, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetchone(sql: str, params=()):
    with db() as conn:
        return one(conn, sql, params)


def fetchall(sql: str, params=()):
    with db() as conn:
        return many(conn, sql, params)
