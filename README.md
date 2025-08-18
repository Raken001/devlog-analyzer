# DevLog Analyzer

A tiny, real-world tool that ingests Git history into SQLite and provides a Streamlit dashboard to explore commit volume, contributor activity, and file-change trends.

---

## Features

- **One-pass ingestion (`ingest.py`)**
  - Parses `git log --numstat`
  - Computes per-commit totals (additions, deletions, files_changed)
  - Writes per-file rows
  - Tags basic “error/fix/bug/…” patterns → `is_fix`, `error_tags`
  - Safe to re-run; upserts by commit hash

- **SQLite data model**
  - Tables: `commits` and `commit_files`
  - Helpful indexes for fast filtering

- **Dashboard (`app.py`)**
  - Filters: date range, authors, file pattern (SQL `LIKE`)
  - Visuals: KPIs, commit volume over time, frequent authors, top changed files, file-change trend for a selected pattern

---

## Data Model

### Table: `commits`
- `hash` (TEXT, PK)
- `author_name` (TEXT)
- `author_email` (TEXT)
- `authored_at` (TEXT ISO 8601)
- `message` (TEXT)
- Per-commit totals:
  - `additions` (INTEGER)
  - `deletions` (INTEGER)
  - `files_changed` (INTEGER)
- Tags:
  - `is_fix` (INTEGER 0/1)
  - `error_tags` (TEXT, comma-joined keywords)

**Indexes**
- By commit date: `authored_at`
- By author: `author_email`, `author_name`
- By hash: `hash` (PRIMARY KEY)

---

### Table: `commit_files`
- `id` (INTEGER, PK AUTOINCREMENT)
- `commit_hash` (TEXT, FK-ish to `commits.hash`)
- `file_path` (TEXT)
- `additions` (INTEGER)
- `deletions` (INTEGER)

**Constraints**
- `UNIQUE(commit_hash, file_path)`

**Indexes**
- By file path: `file_path`
- By commit hash: `commit_hash`

---

## Prerequisites

- Python **3.10+**
- Git available on `PATH` (`git --version`)
- A local Git repository to analyze (clone any public repo if needed)

---

## Setup

Create and activate a virtual environment, then install deps.

Project folder:
```
mkdir devlog-analyzer && cd devlog-analyzer
```

Virtual env (recommended):
```
python -m venv .venv
```

Activate (macOS/Linux):
```
source .venv/bin/activate
```
Activate (Windows PowerShell):
```
.venv\Scripts\Activate.ps1
```
Dependencies:
```
printf "streamlit>=1.38\npandas>=2.2\n" > requirements.txt
pip install --upgrade pip
pip install -r requirements.txt
```
---

## Ingest Git History

If you only have a GitHub URL, clone first:
```sh
git clone https://github.com/<owner>/<repo>
```
Run the ingestor (creates/updates `devlog.db`):
    python ingest.py /path/to/local/repo --db devlog.db

What it does:
- Reads commit headers and `--numstat` lines
- Computes per-commit totals (additions/deletions/files_changed)
- Writes per-file rows (`commit_files`)
- Tags simple “error/fix/bug/…” patterns → `is_fix`, `error_tags`
- Safe to re-run; it upserts by commit hash

---

## Run the Dashboard

    streamlit run app.py

Open the printed local URL (usually `http://localhost:8501`).

---

## Using the Dashboard

**Sidebar filters**
- Date range (from commit timestamps)
- Authors (multiselect)
- File pattern (SQL `LIKE` — examples below)

**Charts & KPIs**
- KPIs: total commits, additions, deletions, fix-tagged commits
- Commit volume over time
- Frequent authors (top 10)
- Top changed files (respecting current filters)
- File-change trend over time (shown when a file pattern is set)

**File pattern examples (SQL `LIKE` syntax)**
- `%search.py%` → any path containing `search.py`
- `%.md` → all Markdown files
- `%/tests/%` → anything under a `tests/` directory
- `src/%` → files directly under `src/`
- `%*.py` is not valid; use `%.py`


---

## Tips & Troubleshooting

- If pandas warns about timezone parsing in future versions, ensure you store `authored_at` as ISO 8601 (UTC) and, when parsing in the app, pass `utc=True` to pandas datetime utilities.
- Very large repos: run ingest from an SSD and consider filtering by path or shallow clones if needed.
- Re-ingest is idempotent per commit hash; you can safely run ingest after pulling new commits.

---

