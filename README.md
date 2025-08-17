DevLog Analyzer 🕵️‍♂️
A tiny, real-world tool that ingests Git history into SQLite and provides a Streamlit dashboard to explore commit volume, contributor activity, and file-change trends.

Features
One-pass ingestion (ingest.py)
Parses git log --numstat, computes per-commit totals, writes per-file rows, and tags basic “error/fix” patterns.

SQLite data model
Tables: commits and commit_files, with helpful indexes.

Dashboard (app.py)

Filters: Date range, authors, and file pattern (SQL LIKE).

Visuals: KPIs, commit volume over time, frequent authors, top changed files, and file-change trend for a selected pattern.

Data Model
commits table
hash (PK)

author_name

author_email

authored_at (ISO string)

message

additions, deletions, files_changed (per-commit totals)

is_fix (0/1)

error_tags (comma-joined keywords)

commit_files table
id (PK)

commit_hash (FK-ish)

file_path

additions

deletions

UNIQUE(commit_hash, file_path)

Indexes are created on commit date, author, file path, and commit hash for fast filtering.

🚦 Prerequisites
Python 3.10+

Git (accessible on your PATH): git --version

A local Git repository to analyze (clone any public repo if needed).

Setup
1. Create a project folder (if you haven't)
Bash

mkdir devlog-analyzer && cd devlog-analyzer
2. Create and activate a virtual environment (recommended)
Bash

# Create the environment
python -m venv .venv

# Activate on macOS/Linux
source .venv/bin/activate

# Activate on Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1
3. Install dependencies
Bash

# Create a requirements.txt file
printf "streamlit>=1.38\npandas>=2.2\n" > requirements.txt

# Install the packages
pip install --upgrade pip
pip install -r requirements.txt
Ingest Git History
The repo path must be a local folder containing a .git directory. If you only have a GitHub URL, clone it first.

Bash

# Example of cloning a repository
git clone https://github.com/<owner>/<repo>
Run the ingestor to create or update the database file (devlog.db).

Bash

python ingest.py /path/to/local/repo --db devlog.db
What it does:

Reads commit headers and numstat lines from Git.

Computes per-commit totals (additions, deletions, files_changed).

Writes a row for each file in each commit to the commit_files table.

Tags simple error patterns (e.g., "error", "fix", "bug") to populate is_fix and error_tags.

The script is safe to re-run; it upserts data based on the commit hash.

📊 Run the Dashboard
Launch the Streamlit application.

Bash

streamlit run app.py
Open the local URL printed in your terminal (usually http://localhost:8501).

Sidebar Filters
Date range: Filter commits by their timestamp.

Authors: A multi-select box to filter by commit authors.

File pattern: An input for a SQL LIKE pattern (e.g., %search.py%, %.md, %/tests/%).

Charts & KPIs
KPIs: Total commits, additions, deletions, and fix-tagged commits.

Commit volume over time: A bar chart showing commit frequency.

Frequent authors: A bar chart of the top 10 contributors.

Top changed files: A table showing the most frequently changed files, respecting the active filters.

File-change trend: A line chart showing changes over time when a file pattern is set.
