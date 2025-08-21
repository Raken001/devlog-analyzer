# app.py
# DevLog Analyzer (dashboard)
# - Sidebar filters: date range, authors, file pattern (SQL LIKE)
# - KPIs: commits, additions, deletions, fix-tagged
# - Charts: commit volume over time, frequent authors, top changed files, file-change trend for a pattern

import os
import ui
from datetime import date
from typing import Optional, List

import pandas as pd
import streamlit as st
import sqlalchemy as sa
from sqlalchemy import text
from dotenv import load_dotenv

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
    # Set up the page
    ui.setup_page()

    # Connect to database
    try:
        engine = connect()
    except Exception as e:
        ui.display_error_message(
            f"Could not connect to MySQL database: {str(e)}", 
            "Make sure the .env file contains the correct DB_URL and the MySQL server is running."
        )

    # Get metadata
    try:
        (min_d, max_d), authors, top_files = get_meta(engine)
    except Exception as e:
        ui.display_error_message(f"Error retrieving metadata from database: {str(e)}")
    
    # Check if we have any data
    if not min_d or not max_d:
        ui.display_error_message("No commits in DB yet.")

    # Set up sidebar filters
    start, end, chosen_authors, file_like, show_errors = ui.setup_sidebar_filters(
        min_d, max_d, authors, top_files
    )

    # Query data
    df = run_query(engine, start.isoformat(), end.isoformat(), chosen_authors, file_like, show_errors)
    if df.empty:
        ui.display_error_message("No commits match your filters.")

    # Display dashboard components
    ui.display_kpis(df)
    ui.display_commit_volume_chart(df)
    ui.display_author_chart(df)
    ui.display_top_files_chart(engine, df["hash"].unique().tolist())
    ui.display_file_trend(engine, file_like, start, end, chosen_authors)
    ui.display_commits_table(df)

if __name__ == "__main__":
    main()
