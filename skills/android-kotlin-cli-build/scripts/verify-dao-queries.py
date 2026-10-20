#!/usr/bin/env python3
"""Run a Room DAO's @Query SELECTs against a real SQLite database.

Why: SQL compiles regardless of whether it returns the right rows. Room's own
validation only checks the schema, and a device is not needed to check the
rows — plain sqlite3 answers it. Extracting the SQL FROM THE DAO SOURCE (rather
than retyping it) is the point: a hand-typed copy tests a query that does not
ship.

Usage:
    # build the db first (see the reference for the schema/seed recipe)
    python3 verify-dao-queries.py \
        --dao app/src/main/kotlin/<pkg>/data/db/dao/PlayHistoryDao.kt \
        --db /tmp/stats.db \
        --params since=0,minListenedMs=30000,limit=5

    # run the same queries with the threshold off, to prove the WHERE clause
    # actually reaches the filter (counts must differ by the skipped rows)
    python3 verify-dao-queries.py --dao ... --db /tmp/stats.db \
        --params since=0,minListenedMs=0,limit=5

Named bind parameters in the Kotlin are substituted textually. Any :param
without a supplied value is reported rather than silently left in the SQL.
"""

import argparse
import os
import re
import sqlite3
import sys

# @Query(""" ... """) followed by the fun declaration. Room's SQL lives in the
# triple-quoted block; single-quoted @Query("SELECT ...") is handled too.
TRIPLE = re.compile(
    r'@Query\(\s*"""(.*?)"""\s*\)\s*(?:\n\s*@\w+\s*)*\n?\s*fun\s+(\w+)\s*\(',
    re.S,
)
SINGLE = re.compile(
    r'@Query\(\s*"((?:[^"\\]|\\.)*)"\s*\)\s*(?:\n\s*@\w+\s*)*\n?\s*fun\s+(\w+)\s*\(',
    re.S,
)
MUTATING = ("INSERT", "UPDATE", "DELETE", "REPLACE")


def extract_queries(path):
    src = open(path, encoding="utf-8").read()
    found = TRIPLE.findall(src) + SINGLE.findall(src)
    return [(sql.strip(), name) for sql, name in found]


def bind(sql, params):
    """Textual substitution of :name bind params. Returns (sql, missing)."""
    missing = []

    def repl(m):
        key = m.group(1)
        if key not in params:
            missing.append(key)
            return m.group(0)
        return params[key]

    return re.sub(r':(\w+)', repl, sql), missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dao", required=True, help="Kotlin DAO file with @Query annotations")
    ap.add_argument("--db", required=True, help="SQLite database to run against")
    ap.add_argument(
        "--params",
        default="",
        help="comma-separated name=value bindings, e.g. since=0,limit=5",
    )
    args = ap.parse_args()

    if not os.path.exists(args.dao):
        sys.exit(f"no such DAO file: {args.dao}")
    if not os.path.exists(args.db):
        sys.exit(f"no such database: {args.db}")

    params = {}
    for pair in filter(None, (p.strip() for p in args.params.split(","))):
        if "=" not in pair:
            sys.exit(f"bad --params entry (want name=value): {pair}")
        name, value = pair.split("=", 1)
        params[name.strip()] = value.strip()

    queries = extract_queries(args.dao)
    if not queries:
        sys.exit("no @Query blocks found — check the file path and the annotation style")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    print(f"{len(queries)} @Query block(s) in {args.dao}\n")
    ran = 0
    for sql, name in queries:
        if any(word in sql.upper() for word in MUTATING):
            print(f"--- {name} (skipped: not a SELECT) ---\n")
            continue

        bound, missing = bind(sql, params)
        if missing:
            print(f"--- {name} (SKIPPED: no value for {sorted(set(missing))}) ---\n")
            continue

        try:
            rows = conn.execute(bound).fetchall()
        except sqlite3.Error as exc:
            print(f"--- {name} ---")
            print(f"SQL ERROR: {exc}\n")
            continue

        ran += 1
        print(f"--- {name} ---")
        if not rows:
            print("(no rows)\n")
            continue
        print(" | ".join(rows[0].keys()))
        for row in rows:
            print(" | ".join("" if v is None else str(v) for v in row))
        print()

    print(f"{ran} query/queries executed.")


if __name__ == "__main__":
    main()
