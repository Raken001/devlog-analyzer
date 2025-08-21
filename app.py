# app.py
# DevLog Analyzer (dashboard)
# - Sidebar filters: date range, authors, file pattern (SQL LIKE)
# - KPIs: commits, additions, deletions, fix-tagged
# - Charts: commit volume over time, frequent authors, top changed files, file-change trend for a pattern

import os
from datetime import date
from typing import Optional, List

import pandas as pd
import streamlit as st
import sqlalchemy as sa
from sqlalchemy import text
from dotenv import load_dotenv

st.set_page_config(page_title="DevLog Analyzer", layout="wide")

# --- Load env variables -------------------------------------------------
load_dotenv()

# --- Connections & cached helpers -------------------------------------------------

@st.cache_resource
def connect():
    # Get connection string from environment variables
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise ValueError("DB_URL not found in environment variables")
    
    # Create SQLAlchemy engine
    engine = sa.create_engine(db_url)
    return engine

@st.cache_data
def get_meta(_engine):
    with _engine.connect() as conn:
        # Min/max dates for defaults
        result = conn.execute(text(
            "SELECT MIN(DATE(authored_at)), MAX(DATE(authored_at)) FROM commits"
        ))
        row = result.fetchone()
        
        # Convert to strings in ISO format if not None
        min_d = row[0].isoformat() if row and row[0] else None
        max_d = row[1].isoformat() if row and row[1] else None

        # Distinct authors for the multiselect
        result = conn.execute(text(
            "SELECT DISTINCT author_name FROM commits ORDER BY author_name"
        ))
        authors = [r[0] for r in result.fetchall()]

        # Popular files for a quick-select (top 50 by commits touching)
        result = conn.execute(text("""
            SELECT file_path FROM (
              SELECT file_path, COUNT(*) AS c
              FROM commit_files
              GROUP BY file_path
              ORDER BY c DESC
              LIMIT 50
            ) AS subq
        """))
        top_files = [r[0] for r in result.fetchall()]

    return (min_d, max_d), authors, top_files

@st.cache_data
def run_query(
    _engine,
    start_iso: str,
    end_iso: str,
    authors: List[str],
    file_like: Optional[str],
    show_errors: bool = False,
):
    where = ["DATE(c.authored_at) BETWEEN :start_date AND :end_date"]
    params = {"start_date": start_iso, "end_date": end_iso}

    if authors:
        placeholders = [f":author_{i}" for i in range(len(authors))]
        where.append(f"c.author_name IN ({', '.join(placeholders)})")
        for i, author in enumerate(authors):
            params[f"author_{i}"] = author

    join = ""
    if file_like:
        join = "JOIN commit_files f ON f.commit_hash = c.hash"
        where.append("f.file_path LIKE :file_pattern")
        params["file_pattern"] = file_like

    if show_errors:
        where.append("(c.is_fix = 1 OR c.error_tags LIKE '%error%' OR c.error_tags LIKE '%bug%')")

    sql = f"""
      SELECT c.hash, c.author_name, c.authored_at, c.additions, c.deletions,
             c.files_changed, c.is_fix, c.message
      FROM commits c
      {join}
      WHERE {" AND ".join(where)}
    """
    
    with _engine.connect() as conn:
        df = pd.read_sql_query(text(sql), conn, params=params)

    if not df.empty:
        # Robust timezone-safe parsing, then drop tz and keep calendar date
        ts = pd.to_datetime(df["authored_at"], errors="coerce", utc=True)
        df["date"] = ts.dt.tz_localize(None).dt.date

    return df

# --- App UI ----------------------------------------------------------------------

def main():
    st.title("DevLog Analyzer (MVP)")

    try:
        engine = connect()
    except Exception as e:
        st.error(f"Could not connect to MySQL database: {str(e)}")
        st.info("Make sure the .env file contains the correct DB_URL and the MySQL server is running.")
        st.stop()

    try:
        (min_d, max_d), authors, top_files = get_meta(engine)
    except Exception as e:
        st.error(f"Error retrieving metadata from database: {str(e)}")
        st.stop()
    
    if not min_d or not max_d:
        st.warning("No commits in DB yet.")
        st.stop()

    # Default to today if we can't parse the dates
    today = date.today()
    
    # Sidebar filters
    c1, c2 = st.sidebar.columns(2)
    try:
        start_date = date.fromisoformat(min_d) if min_d else today
    except (ValueError, TypeError):
        st.warning(f"Could not parse start date: {min_d}. Using today's date.")
        start_date = today
        
    try:
        end_date = date.fromisoformat(max_d) if max_d else today
    except (ValueError, TypeError):
        st.warning(f"Could not parse end date: {max_d}. Using today's date.")
        end_date = today
        
    start = c1.date_input("Start", value=start_date)
    end = c2.date_input("End", value=end_date)
    chosen_authors = st.sidebar.multiselect("Authors", options=authors, default=authors)

    file_hint = st.sidebar.selectbox("Popular files (optional)", [""] + top_files, index=0)
    file_like = st.sidebar.text_input("Or enter file pattern (SQL LIKE)", value=file_hint)
    if file_like and "%" not in file_like and "_" not in file_like:
        file_like = f"%{file_like}%"
    if file_like == "":
        file_like = None

    show_errors = st.sidebar.checkbox("Show only error/fix-tagged commits")

    # Query data
    df = run_query(engine, start.isoformat(), end.isoformat(), chosen_authors, file_like, show_errors)
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
    hashes = df["hash"].unique().tolist()
    if hashes:
        placeholders = [f":hash_{i}" for i in range(len(hashes))]
        params = {f"hash_{i}": hash_val for i, hash_val in enumerate(hashes)}
        
        query = text(f"""
            SELECT file_path, COUNT(*) AS commits_touching
            FROM commit_files
            WHERE commit_hash IN ({', '.join(placeholders)})
            GROUP BY file_path
            ORDER BY commits_touching DESC
            LIMIT 10
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, params)
            rows = result.fetchall()
            
        top_files_df = pd.DataFrame(rows, columns=["file_path", "commits_touching"])
        if not top_files_df.empty:
            st.bar_chart(top_files_df.set_index("file_path"))

    # File-change trend over time (only if user set a pattern)
    if file_like:
        st.subheader("File-change trend over time (matching file filter)")
        where = ["DATE(c.authored_at) BETWEEN :start_date AND :end_date"]
        params = {"start_date": start.isoformat(), "end_date": end.isoformat()}

        if chosen_authors:
            placeholders = [f":auth_{i}" for i in range(len(chosen_authors))]
            where.append(f"c.author_name IN ({', '.join(placeholders)})")
            for i, author in enumerate(chosen_authors):
                params[f"auth_{i}"] = author

        where.append("f.file_path LIKE :file_pattern")
        params["file_pattern"] = file_like

        trend_sql = f"""
          SELECT DATE(c.authored_at) AS day, COUNT(*) AS commits
          FROM commit_files f
          JOIN commits c ON c.hash = f.commit_hash
          WHERE {" AND ".join(where)}
          GROUP BY DATE(c.authored_at)
          ORDER BY day
        """
        
        with engine.connect() as conn:
            trend_df = pd.read_sql_query(text(trend_sql), conn, params=params)
            
        if not trend_df.empty:
            trend_df["day"] = pd.to_datetime(trend_df["day"])
            st.line_chart(trend_df.set_index("day"))

    # Details table
    st.subheader("Commits (filtered)")
    cols = ["authored_at", "author_name", "additions", "deletions", "files_changed", "is_fix", "message", "hash"]
    st.dataframe(df[cols].sort_values("authored_at", ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
