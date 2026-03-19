"""Migrate data from old tables (frames, audio_frames, os_events) to new manifest-based tables.

Usage: python scripts/migrate_to_source_tables.py [--db-path /path/to/engine.db]
"""
import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Migrate frames -> screen_data (if screen_data table exists)
    try:
        conn.execute("SELECT 1 FROM screen_data LIMIT 1")
        screen_exists = True
    except sqlite3.OperationalError:
        screen_exists = False

    if screen_exists:
        existing = conn.execute("SELECT COUNT(*) FROM screen_data").fetchone()[0]
        if existing == 0:
            print("Migrating frames -> screen_data...")
            conn.execute("""
                INSERT INTO screen_data (timestamp, app_name, window_name, text, display_id, image_hash, image_path, processed)
                SELECT timestamp, app_name, window_name, text, display_id, image_hash, image_path, processed
                FROM frames
            """)
            count = conn.execute("SELECT changes()").fetchone()[0]
            print(f"  Migrated {count} rows")
        else:
            print(f"screen_data already has {existing} rows, skipping")

    # Migrate audio_frames -> audio_data
    try:
        conn.execute("SELECT 1 FROM audio_data LIMIT 1")
        audio_exists = True
    except sqlite3.OperationalError:
        audio_exists = False

    if audio_exists:
        existing = conn.execute("SELECT COUNT(*) FROM audio_data").fetchone()[0]
        if existing == 0:
            print("Migrating audio_frames -> audio_data...")
            conn.execute("""
                INSERT INTO audio_data (timestamp, duration_seconds, text, language, source, chunk_path, processed)
                SELECT timestamp, duration_seconds, text, language, source, chunk_path, processed
                FROM audio_frames
            """)
            count = conn.execute("SELECT changes()").fetchone()[0]
            print(f"  Migrated {count} rows")
        else:
            print(f"audio_data already has {existing} rows, skipping")

    # os_events splits into multiple tables (zsh_data, bash_data, safari_data, chrome_data, oslog_data)
    os_event_mappings = {
        "shell_command": {
            "zsh": "zsh_data",
            "bash": "bash_data",
        },
        "browser_url": {
            "safari": "safari_data",
            "chrome": "chrome_data",
        },
        "os_log": {
            "macos": "oslog_data",
        },
    }

    for event_type, source_map in os_event_mappings.items():
        for source, table in source_map.items():
            try:
                conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                continue

            existing = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if existing > 0:
                print(f"{table} already has {existing} rows, skipping")
                continue

            # Map columns based on target table
            if table in ("zsh_data", "bash_data"):
                conn.execute(f"""
                    INSERT INTO {table} (timestamp, command, processed)
                    SELECT timestamp, data, processed
                    FROM os_events
                    WHERE event_type = ? AND source = ?
                """, (event_type, source))
            elif table in ("safari_data", "chrome_data"):
                conn.execute(f"""
                    INSERT INTO {table} (timestamp, url, processed)
                    SELECT timestamp, data, processed
                    FROM os_events
                    WHERE event_type = ? AND source = ?
                """, (event_type, source))
            elif table == "oslog_data":
                conn.execute(f"""
                    INSERT INTO {table} (timestamp, category, data, processed)
                    SELECT timestamp, event_type, data, processed
                    FROM os_events
                    WHERE source = ?
                """, (source,))

            count = conn.execute("SELECT changes()").fetchone()[0]
            print(f"  Migrated {count} rows from os_events ({event_type}/{source}) -> {table}")

    conn.commit()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".observer" / "data" / "engine.db")
    if not Path(db_path).exists():
        print(f"DB not found: {db_path}")
        sys.exit(1)
    migrate(db_path)
