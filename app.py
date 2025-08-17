# app.py
# DevLog Analyzer (dashboard)
# - Sidebar filters: date range, authors, file pattern (SQL LIKE)
# - KPIs: commits, additions, deletions, fix-tagged
# - Charts: commit volume over time, frequent authors, top changed files, file-change trend for a pattern

import os
import sqlite3
from datetime import date
from typing import Optional, List

import pandas as pd
import streamlit as st

st.set_page_config(page_title="DevLog Analyzer", layout="wide")

# --- Connections & cached helpers -------------------------------------------------

@st.cache_resource
def connect(db_path: str):
    # Keep a single connection for the app session
    return sqlite3.connect(db_path, check_same_thread=False)

@st.cache_data
def get_meta(_conn):
    # Min/max dates for defaults
    min_d, max_d = _conn.execute(
        "SELECT MIN(date(authored_at)), MAX(date(authored_at)) FROM commits"
    ).fetchone() or (None, None)

    # Distinct authors for the multiselect
    authors = [r[0] for r in _conn.execute(
        "SELECT DISTINCT author_name FROM commits ORDER BY author_name"
    ).fetchall()]

    # Popular files for a quick-select (top 50 by commits touching)
    top_files = [r[0] for r in _conn.execute("""
        SELECT file_path FROM (
          SELECT file_path, COUNT(*) AS c
          FROM commit_files
          GROUP BY file_path
          ORDER BY c DESC
          LIMIT 50
        )
    """).fetchall()]

    return (min_d, max_d), authors, top_files

@st.cache_data
def run_query(
    _conn,
    start_iso: str,
    end_iso: str,
    authors: List[str],
    file_like: Optional[str],
):
    where = ["date(c.authored_at) BETWEEN ? AND ?"]
    params: List[object] = [start_iso, end_iso]

    if authors:
        where.append("c.author_name IN ({})".format(",".join("?" * len(authors))))
        params.extend(authors)

    join = ""
    if file_like:
        join = "JOIN commit_files f ON f.commit_hash = c.hash"
        where.append("f.file_path LIKE ?")
        params.append(file_like)

    sql = f"""
      SELECT c.hash, c.author_name, c.authored_at, c.additions, c.deletions,
             c.files_changed, c.is_fix, c.message
      FROM commits c
      {join}
      WHERE {" AND ".join(where)}
    """
    df = pd.read_sql_query(sql, _conn, params=params)

    if not df.empty:
        # Robust timezone-safe parsing, then drop tz and keep calendar date
        ts = pd.to_datetime(df["authored_at"], errors="coerce", utc=True)
        df["date"] = ts.dt.tz_localize(None).dt.date

    return df

# --- App UI ----------------------------------------------------------------------

def main():
    st.title("DevLog Analyzer (MVP)")

    db_path = st.sidebar.text_input("SQLite DB path", "devlog.db")
    if not os.path.exists(db_path):
        st.info("DB not found. Run an ingestor first (e.g., `python ingest_files.py <repo>`).")
        st.stop()

    conn = connect(db_path)
    (min_d, max_d), authors, top_files = get_meta(conn)
    if not min_d or not max_d:
        st.warning("No commits in DB yet.")
        st.stop()

    # Sidebar filters
    c1, c2 = st.sidebar.columns(2)
    start = c1.date_input("Start", value=date.fromisoformat(min_d))
    end = c2.date_input("End", value=date.fromisoformat(max_d))
    chosen_authors = st.sidebar.multiselect("Authors", options=authors, default=authors)

    file_hint = st.sidebar.selectbox("Popular files (optional)", [""] + top_files, index=0)
    file_like = st.sidebar.text_input("Or enter file pattern (SQL LIKE)", value=file_hint)
    if file_like and "%" not in file_like and "_" not in file_like:
        file_like = f"%{file_like}%"
    if file_like == "":
        file_like = None

    # Query data
    df = run_query(conn, start.isoformat(), end.isoformat(), chosen_authors, file_like)
    if df.empty:
        st.warning("No commits match your filters.")
        st.stop()

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Commits", f"{len(df):,}")
    k2.metric("Additions", int(df["additions"].sum()))
    k3.metric("Deletions", int(df["deletions"].sum()))
    k4.metric("Fix-tagged", int(df["is_fix"].sum()))

    # Commit volume over time
    st.subheader("Commit volume over time")
    by_day = df.groupby("date").size().rename("commits").reset_index()
    st.line_chart(by_day.set_index("date"))

    # Frequent authors
    st.subheader("Frequent authors")
    top_auth = (
        df.groupby("author_name").size()
        .sort_values(ascending=False)
        .head(10)
        .rename("commits")
        .reset_index()
    )
    st.bar_chart(top_auth.set_index("author_name"))

    # Top changed files within current filters
    st.subheader("Top changed files (within current filters)")
    hashes = tuple(df["hash"].unique().tolist())
    if hashes:
        q_marks = ",".join("?" * len(hashes))
        rows = conn.execute(
            f"""
            SELECT file_path, COUNT(*) AS commits_touching
            FROM commit_files
            WHERE commit_hash IN ({q_marks})
            GROUP BY file_path
            ORDER BY commits_touching DESC
            LIMIT 10
            """,
            hashes,
        ).fetchall()
        top_files_df = pd.DataFrame(rows, columns=["file_path", "commits_touching"])
        if not top_files_df.empty:
            st.bar_chart(top_files_df.set_index("file_path"))

    # File-change trend over time (only if user set a pattern)
    if file_like:
        st.subheader("File-change trend over time (matching file filter)")
        where = ["date(c.authored_at) BETWEEN ? AND ?"]
        params: List[object] = [start.isoformat(), end.isoformat()]

        if chosen_authors:
            where.append("c.author_name IN ({})".format(",".join("?" * len(chosen_authors))))
            params.extend(chosen_authors)

        where.append("f.file_path LIKE ?")
        params.append(file_like)

        trend_sql = f"""
          SELECT date(c.authored_at) AS day, COUNT(*) AS commits
          FROM commit_files f
          JOIN commits c ON c.hash = f.commit_hash
          WHERE {" AND ".join(where)}
          GROUP BY date(c.authored_at)
          ORDER BY day
        """
        trend_df = pd.read_sql_query(trend_sql, conn, params=params)
        if not trend_df.empty:
            trend_df["day"] = pd.to_datetime(trend_df["day"])
            st.line_chart(trend_df.set_index("day"))

    # Details table
    st.subheader("Commits (filtered)")
    cols = ["authored_at", "author_name", "additions", "deletions", "files_changed", "is_fix", "message", "hash"]
    st.dataframe(df[cols].sort_values("authored_at", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
