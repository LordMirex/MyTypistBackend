# MyTypist Scripts & Optimization Guide

## Database Optimization Scripts

### SQLite WAL Mode Setup

```bash
#!/bin/bash
# setup_sqlite_wal.sh - Enable WAL mode for better concurrency

DB_PATH="./mytypist.db"

if [ -f "$DB_PATH" ]; then
    echo "Enabling WAL mode for SQLite database..."
    sqlite3 "$DB_PATH" "PRAGMA journal_mode=WAL;"
    sqlite3 "$DB_PATH" "PRAGMA cache_size=10000;"
    sqlite3 "$DB_PATH" "PRAGMA synchronous=NORMAL;"
    sqlite3 "$DB_PATH" "PRAGMA busy_timeout=30000;"
    echo "WAL mode enabled successfully"
else
    echo "Database file not found: $DB_PATH"
    exit 1
fi
