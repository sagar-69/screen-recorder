#!/usr/bin/env python3
"""macOS TCC Screen Recording permission list reader.

Reads the TCC (Transparency, Consent, and Control) database to list apps
that have been granted Screen Recording permission.

Requirements:
  - macOS 13+
  - Full Disk Access for the terminal / Python running this script
    (without it, reading the system TCC.db will fail with a permission error)

Usage:
  python3 spike/macos_tcc_reader.py
"""

import sqlite3
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# System TCC database (requires Full Disk Access)
SYSTEM_TCC_DB = "/Library/Application Support/com.apple.TCC/TCC.db"

# User TCC database (readable without FDA on older macOS, may not have screen recording)
USER_TCC_DB = os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db")

# The service name for Screen Recording in TCC
SCREEN_CAPTURE_SERVICE = "kTCCServiceScreenCapture"


def read_tcc_db(db_path: str) -> list[dict]:
    """Read screen capture entries from a TCC database."""
    results = []

    if not os.path.exists(db_path):
        print(f"  Database not found: {db_path}", file=sys.stderr)
        return results

    try:
        # Connect read-only
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # List all tables to understand the schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  Tables in {os.path.basename(db_path)}: {tables}")

        # Try to read the access table
        # Schema varies between macOS versions
        try:
            cursor.execute("""
                SELECT * FROM access
                WHERE service = ?
            """, (SCREEN_CAPTURE_SERVICE,))

            columns = [description[0] for description in cursor.description]
            print(f"  Columns: {columns}")

            for row in cursor.fetchall():
                entry = dict(zip(columns, row))

                # Decode common fields
                record = {
                    "db": os.path.basename(os.path.dirname(db_path)),
                    "service": entry.get("service", ""),
                    "client": entry.get("client", ""),
                    "client_type": entry.get("client_type", ""),
                    "auth_value": entry.get("auth_value", ""),
                    "auth_reason": entry.get("auth_reason", ""),
                    "last_modified": "",
                    "raw": {k: str(v) for k, v in entry.items()},
                }

                # Decode last_modified timestamp (CoreData timestamp: seconds since 2001-01-01)
                last_mod = entry.get("last_modified")
                if last_mod and isinstance(last_mod, (int, float)) and last_mod > 0:
                    try:
                        # Core Data epoch is 2001-01-01 00:00:00 UTC
                        core_data_epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
                        from datetime import timedelta
                        ts = core_data_epoch + timedelta(seconds=last_mod)
                        record["last_modified"] = ts.isoformat()
                    except (ValueError, OverflowError):
                        record["last_modified"] = str(last_mod)

                # Decode auth_value
                auth_map = {0: "denied", 1: "unknown", 2: "allowed", 3: "limited"}
                auth_val = entry.get("auth_value", -1)
                record["auth_meaning"] = auth_map.get(auth_val, f"unknown({auth_val})")

                results.append(record)

        except sqlite3.OperationalError as e:
            print(f"  Error reading access table: {e}", file=sys.stderr)

        conn.close()
    except sqlite3.OperationalError as e:
        print(f"  Cannot open {db_path}: {e}", file=sys.stderr)
        if "unable to open" in str(e).lower() or "not authorized" in str(e).lower():
            print("  → This likely means Full Disk Access is NOT granted.", file=sys.stderr)
            print("  → Grant Full Disk Access to Terminal (or your IDE) in:", file=sys.stderr)
            print("    System Settings → Privacy & Security → Full Disk Access", file=sys.stderr)

    return results


def emit_events(entries: list[dict]) -> None:
    """Emit schema v1 events for each TCC entry that has screen recording permission."""
    for entry in entries:
        if entry.get("auth_meaning") == "allowed":
            event = {
                "v": 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "os": "macos",
                "sensor": "tcc_list",
                "signal": "tcc_permission_granted",
                "class": "reliable",
                "app": {
                    "name": entry["client"],
                    "pid": 0,
                    "path": "",
                    "publisher": "",
                    "signed": False,
                },
                "method_hint": "screen_recording",
                "ended": False,
                "session_id": f"tcc:{entry['client']}",
                "detail": {
                    "auth_value": entry.get("auth_value"),
                    "last_modified": entry.get("last_modified"),
                    "db_source": entry.get("db"),
                },
            }
            print(json.dumps(event))


def main():
    print("=" * 60)
    print("macOS TCC Screen Recording Permission Reader")
    print("=" * 60)
    print()

    all_entries = []

    # Try system TCC database first
    print(f"[1] Reading system TCC database: {SYSTEM_TCC_DB}")
    system_entries = read_tcc_db(SYSTEM_TCC_DB)
    all_entries.extend(system_entries)
    print(f"    Found {len(system_entries)} screen recording entries")
    print()

    # Try user TCC database
    print(f"[2] Reading user TCC database: {USER_TCC_DB}")
    user_entries = read_tcc_db(USER_TCC_DB)
    all_entries.extend(user_entries)
    print(f"    Found {len(user_entries)} screen recording entries")
    print()

    # Summary
    print("=" * 60)
    print(f"Total screen recording entries: {len(all_entries)}")
    print()

    if not all_entries:
        print("No entries found. Possible reasons:")
        print("  - Full Disk Access not granted (required for system TCC.db)")
        print("  - No apps have requested Screen Recording permission")
        print()
    else:
        print("Entries:")
        for entry in all_entries:
            status = entry.get("auth_meaning", "unknown")
            client = entry.get("client", "unknown")
            last_mod = entry.get("last_modified", "unknown")
            print(f"  [{status:>7}] {client}")
            print(f"           Last modified: {last_mod}")
            print(f"           Raw auth_value: {entry.get('auth_value')}")
            print()

    # Emit schema v1 events to stdout
    print("=" * 60)
    print("Schema v1 events (for apps with permission granted):")
    print("-" * 60)
    emit_events(all_entries)


if __name__ == "__main__":
    main()
