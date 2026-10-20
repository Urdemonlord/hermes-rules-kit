#!/usr/bin/env python3
"""Validate a Room migration headless, by replaying Room's own schema check in SQLite.

Room validates a migration by comparing the live database's schema against the schema it expects
from the compiled entities. That check is pure SQLite introspection, so it can be reproduced
without a device: build a database from the OLD exported schema, run the migration statements,
then compare against the NEW exported schema using the same normalisations Room applies.

This catches migrations that compile cleanly but crash on first open in the user's device — the
one class of Android bug that no build, lint, or unit test surfaces.

Usage:
    python3 validate-room-migration.py \
        --schemas app/schemas/com.example.data.db.AppDatabase \
        --from 2 --to 3 \
        --sql migration.sql

--sql is a file of raw SQL statements, one per line (the bodies of your Migration.migrate()
execSQL calls, in order). Blank lines and lines starting with '--' are ignored.

Exit code 0 = Room would accept the migration. 1 = it would reject it (details printed).

Note on defaults: Room treats an absent default, an empty string, and the literal 'NULL' as the
same thing for a nullable column. A migration written as `ADD COLUMN x TEXT DEFAULT NULL` stores
the string 'NULL' and is therefore *accepted* by this normalisation only if Room's expectation is
also empty — it is not, which is exactly why that form is rejected in practice. Prefer
`ADD COLUMN x TEXT`.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


def load_schema(schemas_dir: Path, version: int) -> dict:
    path = schemas_dir / f"{version}.json"
    if not path.exists():
        sys.exit(f"schema not found: {path}")
    return json.loads(path.read_text())["database"]


def entity(db: dict, table: str) -> dict:
    for e in db["entities"]:
        if e["tableName"] == table:
            return e
    sys.exit(f"table {table!r} not present in schema v{db['version']}")


def normalize_default(value):
    """Mirror Room's TableInfo.normalizeDefaultValue."""
    if value is None:
        return None
    value = value.strip()
    return None if value in ("", "NULL", "null") else value


def read_table(conn: sqlite3.Connection, table: str) -> dict:
    columns = {}
    for row in conn.execute(f"PRAGMA table_info(`{table}`)"):
        _, name, ctype, notnull, dflt, _pk = row
        columns[name] = {
            "type": (ctype or "").upper(),
            "notNull": bool(notnull),
            "default": normalize_default(dflt),
        }
    indices = {}
    for row in conn.execute(f"PRAGMA index_list(`{table}`)"):
        name, origin = row[1], row[3]
        if origin == "pk" or name.startswith("sqlite_autoindex"):
            continue
        indices[name] = {
            "unique": bool(row[2]),
            "columns": [r[2] for r in conn.execute(f"PRAGMA index_info(`{name}`)")],
        }
    return {"columns": columns, "indices": indices}


def build_from_schema(conn: sqlite3.Connection, db: dict) -> None:
    for e in db["entities"]:
        table = e["tableName"]
        conn.execute(e["createSql"].replace("${TABLE_NAME}", table))
        for idx in e.get("indices", []):
            conn.execute(idx["createSql"].replace("${TABLE_NAME}", table))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS room_master_table "
        "(id INTEGER PRIMARY KEY, identity_hash TEXT)"
    )
    conn.execute(
        "INSERT OR REPLACE INTO room_master_table VALUES (42, ?)", (db["identityHash"],)
    )
    conn.commit()


def expected(db: dict, table: str) -> dict:
    e = entity(db, table)
    columns = {
        f["columnName"]: {
            "type": f["affinity"].upper(),
            "notNull": f["notNull"],
            "default": normalize_default(f.get("defaultValue")),
        }
        for f in e["fields"]
    }
    indices = {
        i["name"]: {"unique": i["unique"], "columns": i["columnNames"]}
        for i in e.get("indices", [])
    }
    return {"columns": columns, "indices": indices}


def compare(conn: sqlite3.Connection, new_db: dict) -> list[str]:
    problems: list[str] = []
    for e in new_db["entities"]:
        table = e["tableName"]
        actual = read_table(conn, table)
        want = expected(new_db, table)

        missing = set(want["columns"]) - set(actual["columns"])
        extra = set(actual["columns"]) - set(want["columns"])
        if missing:
            problems.append(f"{table}: missing columns {sorted(missing)}")
        if extra:
            problems.append(f"{table}: unexpected columns {sorted(extra)}")

        for name, w in want["columns"].items():
            a = actual["columns"].get(name)
            if a is None:
                continue
            if a != w:
                problems.append(
                    f"{table}.{name}: got {a}, Room expects {w}"
                )

        miss_idx = set(want["indices"]) - set(actual["indices"])
        extra_idx = set(actual["indices"]) - set(want["indices"])
        if miss_idx:
            problems.append(f"{table}: missing indices {sorted(miss_idx)}")
        if extra_idx:
            problems.append(f"{table}: unexpected indices {sorted(extra_idx)}")
        for name, w in want["indices"].items():
            a = actual["indices"].get(name)
            if a is not None and a != w:
                problems.append(f"{table}.{name}: got {a}, Room expects {w}")
    return problems


def split_statements(raw: str) -> list[str]:
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        out.append(line.rstrip(";"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schemas", required=True,
                    help="directory holding the exported <version>.json files")
    ap.add_argument("--from", dest="from_version", type=int, required=True)
    ap.add_argument("--to", dest="to_version", type=int, required=True)
    ap.add_argument("--sql", required=True,
                    help="file with the migration's SQL statements, one per line")
    args = ap.parse_args()

    schemas = Path(args.schemas)
    old_db = load_schema(schemas, args.from_version)
    new_db = load_schema(schemas, args.to_version)
    statements = split_statements(Path(args.sql).read_text())

    conn = sqlite3.connect(":memory:")
    build_from_schema(conn, old_db)
    print(f"built schema v{args.from_version} "
          f"({len(old_db['entities'])} tables, hash {old_db['identityHash'][:12]}…)")

    for stmt in statements:
        try:
            conn.execute(stmt)
        except sqlite3.Error as exc:
            print(f"FAILED executing: {stmt}\n  {exc}")
            return 1
    conn.execute("UPDATE room_master_table SET identity_hash = ? WHERE id = 42",
                 (new_db["identityHash"],))
    conn.commit()
    print(f"applied {len(statements)} migration statement(s)")

    problems = compare(conn, new_db)
    if problems:
        print(f"\nMIGRATION v{args.from_version} -> v{args.to_version} REJECTED:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"\nMIGRATION v{args.from_version} -> v{args.to_version}: Room would accept it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
