DevLog Analyzer 

A tiny, real-world tool that ingests Git history into SQLite and provides a Streamlit dashboard to explore commit volume, contributor activity, and file-change trends. 

✨ Features

One-pass ingestion (ingest.py)
Parses git log --numstat, computes per-commit totals, writes per-file rows, and tags basic “error/fix” patterns.

SQLite data model
Tables: commits and commit_files, with helpful indexes.

Dashboard (app.py)
Filters: date range, authors, and file pattern (SQL LIKE).
Visuals: KPIs, commit volume over time, frequent authors, top changed files, and file-change trend for a selected pattern.

🧱 Data Model

commits

hash (PK), author_name, author_email, authored_at (ISO string), message

additions, deletions, files_changed (per-commit totals)

is_fix (0/1), error_tags (comma-joined keywords)

commit_files

id (PK), commit_hash (FK-ish), file_path, additions, deletions

UNIQUE(commit_hash, file_path)

Indexes on commit date, author, file path, and commit hash for fast filtering.

🚦 Prerequisites

Python 3.10+

Git (accessible on your PATH): git --version

A local Git repository to analyze (clone any public repo if needed)

⚙️ Setup
# create project folder (if you haven't)
mkdir devlog-analyzer && cd devlog-analyzer

# (recommended) virtual env
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows (powershell)
# .venv\Scripts\Activate.ps1

# dependencies
printf "streamlit>=1.38\npandas>=2.2\n" > requirements.txt
pip install --upgrade pip
pip install -r requirements.txt


Optional .gitignore:

.venv/
__pycache__/
devlog.db

📥 Ingest Git History

The repo path must be local (a folder with a .git directory).
If you only have a GitHub URL, clone it first:
git clone https://github.com/<owner>/<repo>

# run the ingestor (creates/updates devlog.db)
python ingest.py /path/to/local/repo --db devlog.db


What it does:

Reads commit headers and numstat lines

Computes per-commit totals (additions/deletions/files_changed)

Writes per-file rows (commit_files)

Tags simple “error/fix/bug/…” patterns → is_fix, error_tags

Safe to re-run; it upserts by commit hash.

📊 Run the Dashboard
streamlit run app.py


Open the printed local URL (usually http://localhost:8501).

Sidebar filters

Date range (from commit timestamps)

Authors (multiselect)

File pattern (SQL LIKE — e.g., %search.py%, %.md, %/tests/%)

Charts & KPIs

KPIs: total commits, additions, deletions, fix-tagged commits

Commit volume over time

Frequent authors (top 10)

Top changed files (respecting current filters)

File-change trend over time (when a file pattern is set)