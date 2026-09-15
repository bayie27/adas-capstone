"""Read selected audit and session evidence from an isolated ADAS database."""

import argparse
import json
import sqlite3
from pathlib import Path


def rows(connection, query):
    return [dict(row) for row in connection.execute(query)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    connection = sqlite3.connect(args.database)
    connection.row_factory = sqlite3.Row
    evidence = {
        "recent_logouts": rows(
            connection,
            "select audit_id, action, username, result, target_ref, created_at "
            "from audit_log where action = 'LOGOUT' order by audit_id desc limit 3",
        ),
        "recent_sessions": rows(
            connection,
            "select session_id, revoked_at, revocation_reason "
            "from auth_session order by created_at desc limit 3",
        ),
    }
    text = json.dumps(evidence, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
