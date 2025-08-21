# ui.py
# Contains UI components for DevLog Analyzer dashboard

import streamlit as st
from datetime import date
from typing import Optional, List, Tuple
import pandas as pd
import sqlalchemy as sa

def setup_page():
    """Set up basic page configuration"""
    st.set_page_config(page_title="DevLog Analyzer", layout="wide")
    st.title("DevLog Analyzer")

def display_error_message(message: str, info: Optional[str] = None):
    """Display error message and optional info"""
    st.error(message)
    if info:
        st.info(info)
    st.stop()

def setup_sidebar_filters(min_d, max_d, authors, top_files):
    """Set up and render sidebar filters"""
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
    
    return start, end, chosen_authors, file_like, show_errors

def display_kpis(df):
    """Display KPI metrics in the dashboard"""
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Commits", f"{len(df):,}")
    k2.metric("Additions", int(df["additions"].sum()))
    k3.metric("Deletions", int(df["deletions"].sum()))
    k4.metric("Fix-tagged", int(df["is_fix"].sum()))

def display_commit_volume_chart(df):
    """Display commit volume over time chart"""
    st.subheader("Commit volume over time")
    by_day = df.groupby("date").size().rename("commits").reset_index()
    st.line_chart(by_day.set_index("date"))

def display_author_chart(df):
    """Display frequent authors chart"""
    st.subheader("Frequent authors")
    top_auth = (
        df.groupby("author_name").size()
        .sort_values(ascending=False)
        .head(10)
        .rename("commits")
        .reset_index()
    )
    st.bar_chart(top_auth.set_index("author_name"))

def display_top_files_chart(engine, hashes):
    """Display top changed files chart"""
    st.subheader("Top changed files (within current filters)")
    if hashes:
        placeholders = [f":hash_{i}" for i in range(len(hashes))]
        params = {f"hash_{i}": hash_val for i, hash_val in enumerate(hashes)}
        
        query = sa.text(f"""
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

def display_file_trend(engine, file_like, start, end, chosen_authors):
    """Display file-change trend over time for specific file pattern"""
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
            trend_df = pd.read_sql_query(sa.text(trend_sql), conn, params=params)
            
        if not trend_df.empty:
            trend_df["day"] = pd.to_datetime(trend_df["day"])
            st.line_chart(trend_df.set_index("day"))

def display_commits_table(df):
    """Display details table of filtered commits"""
    st.subheader("Commits (filtered)")
    cols = ["authored_at", "author_name", "additions", "deletions", "files_changed", "is_fix", "message", "hash"]
    st.dataframe(df[cols].sort_values("authored_at", ascending=False), use_container_width=True)
