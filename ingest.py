"""
ingest.py — one-pass ingestor for DevLog Analyzer
- Parses `git log --numstat` (headers + per-file changes)
- Computes per-commit totals (additions, deletions, files_changed)
- Tags basic error/fix patterns from commit messages
- Upserts into SQLite (`commits`, `commit_files`)
- Creates schema if missing

Usage:
  python ingest.py /path/to/repo --db devlog.db
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS commits (
  hash TEXT PRIMARY KEY,
  author_name TEXT NOT NULL,
  author_email TEXT NOT NULL,
  authored_at TEXT NOT NULL,
  message TEXT NOT NULL,
  additions INTEGER NOT NULL DEFAULT 0,
  deletions INTEGER NOT NULL DEFAULT 0,
  files_changed INTEGER NOT NULL DEFAULT 0,
  is_fix INTEGER NOT NULL DEFAULT 0,
  error_tags TEXT
);
CREATE TABLE IF NOT EXISTS commit_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  commit_hash TEXT NOT NULL,
  file_path TEXT NOT NULL,
  additions INTEGER NOT NULL DEFAULT 0,
  deletions INTEGER NOT NULL DEFAULT 0,
  UNIQUE(commit_hash, file_path)
);
CREATE INDEX IF NOT EXISTS idx_commits_date   ON commits(authored_at);
CREATE INDEX IF NOT EXISTS idx_commits_author ON commits(author_name);
CREATE INDEX IF NOT EXISTS idx_files_path     ON commit_files(file_path);
CREATE INDEX IF NOT EXISTS idx_files_commit   ON commit_files(commit_hash);
"""

# Simple “error pattern” tagger (MVP but useful)
TAG_RE = re.compile(
    r"\b(fix|bug|error|fail|failed|failure|exception|panic|hotfix|issue|revert|patch|defect|fatal|crash|broken|regress(?:ion)?)\b",
    re.IGNORECASE,
)

GIT_ARGS = [
    "log",
    "--numstat",
    "--date=iso-strict",
    "--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s",
]

UPSERT_COMMIT = """
INSERT INTO commits(hash, author_name, author_email, authored_at, message,
                    additions, deletions, files_changed, is_fix, error_tags)
VALUES(:hash, :author_name, :author_email, :authored_at, :message,
       :additions, :deletions, :files_changed, :is_fix, :error_tags)
ON CONFLICT(hash) DO UPDATE SET
  author_name=excluded.author_name,
  author_email=excluded.author_email,
  authored_at=excluded.authored_at,
  message=excluded.message,
  additions=excluded.additions,
  deletions=excluded.deletions,
  files_changed=excluded.files_changed,
  is_fix=excluded.is_fix,
  error_tags=excluded.error_tags;
"""

DELETE_FILES_FOR_COMMIT = "DELETE FROM commit_files WHERE commit_hash = ?"
INSERT_FILE_ROW = "INSERT OR IGNORE INTO commit_files(commit_hash, file_path, additions, deletions) VALUES(?, ?, ?, ?)"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def ingest_full(repo: Path, db: Path) -> None:
    if not (repo / ".git").exists():
        raise SystemExit(f"Not a git repo: {repo}")

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    ensure_schema(conn)

    print(f"[ingest] repo={repo}")
    proc = subprocess.Popen(
        ["git", "-C", str(repo), *GIT_ARGS],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not proc.stdout:
        raise SystemExit("Failed to run `git log`.")

    current = None
    file_rows = []
    headers_seen = commits_written = files_written = 0

    def flush():
        nonlocal current, file_rows, commits_written, files_written
        if not current:
            return
        # tag error patterns from the subject line 
        tags = {m.group(1).lower() for m in TAG_RE.finditer(current["message"] or "")}
        current["is_fix"] = 1 if tags else 0
        current["error_tags"] = ",".join(sorted(tags)) if tags else None

        cur.execute(UPSERT_COMMIT, current)
        cur.execute(DELETE_FILES_FOR_COMMIT, (current["hash"],))
        if file_rows:
            cur.executemany(INSERT_FILE_ROW, file_rows)
            files_written += len(file_rows)

        commits_written += 1
        current = None
        file_rows = []

    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t", 4)

        # Header line?
        if len(parts) == 5 and len(parts[0]) == 40:
            # finish previous commit
            flush()
            c_hash, a_name, a_email, authored_at, subject = parts
            current = {
                "hash": c_hash,
                "author_name": a_name,
                "author_email": a_email,
                "authored_at": authored_at,
                "message": subject,
                "additions": 0,
                "deletions": 0,
                "files_changed": 0,
                "is_fix": 0,
                "error_tags": None,
            }
            headers_seen += 1
            continue

        # Numstat line? (add \t del \t path)
        if len(parts) == 3 and current is not None:
            a_raw, d_raw, path = parts
            a = int(a_raw) if a_raw.isdigit() else 0  # '-' for binary → 0
            d = int(d_raw) if d_raw.isdigit() else 0
            current["additions"] += a
            current["deletions"] += d
            current["files_changed"] += 1
            file_rows.append((current["hash"], path, a, d))

    # final commit
    flush()
    conn.commit()
    ret = proc.wait()
    conn.close()

    print(f"[ingest] git exit code: {ret}")
    print(f"[ingest] commits parsed: {headers_seen}")
    print(f"[ingest] commits written: {commits_written}")
    print(f"[ingest] file rows written: {files_written}")
    print(f"[ingest] db: {db.resolve()}")


def main():
    ap = argparse.ArgumentParser(description="DevLog Analyzer - full ingestor")
    ap.add_argument("repo", type=Path, help="Path to a local git repo")
    ap.add_argument("--db", type=Path, default=Path("devlog.db"), help="SQLite path")
    args = ap.parse_args()
    ingest_full(args.repo, args.db)


if __name__ == "__main__":
    main()
