"""
ingest.py — one-pass ingestor for DevLog Analyzer
- Parses `git log --numstat` (headers + per-file changes)
- Computes per-commit totals (additions, deletions, files_changed)
- Tags basic error/fix patterns from commit messages
- Upserts into MySQL (`commits`, `commit_files`) using SQLAlchemy
- Creates schema if missing

Usage:
  python ingest.py /path/to/repo
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import text
from dotenv import load_dotenv

# Simple "error pattern" tagger (MVP but useful)
TAG_RE = re.compile(
    r"\b(fix|bug|error|fail|failed|failure|exception|panic|hotfix|issue|revert|patch|defect|fatal|crash|broken|regress(?:ion)?)\b",
    re.IGNORECASE,
)

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
ON DUPLICATE KEY UPDATE
  author_name=VALUES(author_name),
  author_email=VALUES(author_email),
  authored_at=VALUES(authored_at),
  message=VALUES(message),
  additions=VALUES(additions),
  deletions=VALUES(deletions),
  files_changed=VALUES(files_changed),
  is_fix=VALUES(is_fix),
  error_tags=VALUES(error_tags)
"""

DELETE_FILES_FOR_COMMIT = "DELETE FROM commit_files WHERE commit_hash = :commit_hash"
INSERT_FILE_ROW = """
INSERT INTO commit_files(commit_hash, file_path, additions, deletions) 
VALUES(:commit_hash, :file_path, :additions, :deletions)
ON DUPLICATE KEY UPDATE
  additions=VALUES(additions),
  deletions=VALUES(deletions)
"""


# Load environment variables
load_dotenv()

def get_engine():
    # Get connection string from environment variables
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise ValueError("DB_URL not found in environment variables")
    
    # Create SQLAlchemy engine
    return sa.create_engine(db_url)

def ensure_schema(engine: sa.Engine) -> None:
    # Read schema from file
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    schema_sql = schema_path.read_text()
    
    # MySQL doesn't support executing multiple statements at once through SQLAlchemy
    # We need to split and execute them individually
    statements = schema_sql.strip().split(';')
    
    with engine.connect() as conn:
        for statement in statements:
            if statement.strip():
                # Skip comments
                if not statement.strip().startswith('--'):
                    conn.execute(text(statement))
        conn.commit()


def ingest_full(repo: Path) -> None:
    if not (repo / ".git").exists():
        raise SystemExit(f"Not a git repo: {repo}")

    engine = get_engine()
    ensure_schema(engine)

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

    # Create a session to work with the database
    with engine.connect() as conn:
        def flush():
            nonlocal current, file_rows, commits_written, files_written
            if not current:
                return
            # tag error patterns from the subject line 
            tags = {m.group(1).lower() for m in TAG_RE.finditer(current["message"] or "")}
            current["is_fix"] = 1 if tags else 0
            current["error_tags"] = ",".join(sorted(tags)) if tags else None

            # Execute the UPSERT_COMMIT with named parameters
            conn.execute(text(UPSERT_COMMIT), current)
            
            # Delete existing file entries for this commit
            conn.execute(text(DELETE_FILES_FOR_COMMIT), {"commit_hash": current["hash"]})
            
            # Insert file records
            if file_rows:
                for file_hash, file_path, adds, dels in file_rows:
                    file_data = {
                        "commit_hash": file_hash,
                        "file_path": file_path,
                        "additions": adds,
                        "deletions": dels
                    }
                    conn.execute(text(INSERT_FILE_ROW), file_data)
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

    print(f"[ingest] git exit code: {ret}")
    print(f"[ingest] commits parsed: {headers_seen}")
    print(f"[ingest] commits written: {commits_written}")
    print(f"[ingest] file rows written: {files_written}")
    print(f"[ingest] db: MySQL database from .env")


def main():
    ap = argparse.ArgumentParser(description="DevLog Analyzer - full ingestor")
    ap.add_argument("repo", type=Path, help="Path to a local git repo")
    args = ap.parse_args()
    
    try:
        ingest_full(args.repo)
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure the .env file exists and contains DB_URL")
    except Exception as e:
        print(f"Error: {e}")
        print("Check your database connection settings in the .env file")


if __name__ == "__main__":
    main()
