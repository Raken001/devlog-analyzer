# Devlog Analyzer: Design Document

## Overview

Devlog Analyzer is a Python-based tool for ingesting, analyzing, and peeking into development log data stored in a SQLite database (`devlog.db`). The project provides scripts for importing log files, validating schema, extracting headers, totals, and tags, and querying the database for insights. The design emphasizes modularity, extensibility, and ease of use for developers who want to analyze their development logs.

## Goals

- **Automate ingestion** of devlog files into a structured database.
- **Validate and enforce schema** consistency for reliable data analysis.
- **Provide utilities** for extracting headers, totals, and tags from logs.
- **Enable querying and peeking** into the database for quick insights.
- **Support extensibility** for new log formats and analysis features.

## Architecture

### Components

1. **Database Layer**
   - Uses SQLite (`devlog.db`) for storage.
   - Schema defined in `schema.py` and validated by `check_schema.py`.
   - Handles tables for logs, headers, totals, and tags.

2. **Ingestion Layer**
   - `ingest.py`: Main entry for ingesting log files.
   - `ingest_files.py`, `ingest_headers.py`, `ingest_totals.py`: Specialized ingestion scripts for different data types.
   - Handles parsing, transformation, and insertion into the database.

3. **Peek/Query Layer**
   - `peek.py`: Main entry for querying the database.
   - `peek_files.py`, `peek_tags.py`, `peek_totals.py`: Specialized scripts for extracting specific insights.
   - Provides CLI and programmatic access to data.

4. **Validation Layer**
   - `check_schema.py`: Ensures database schema matches expected structure.
   - `tag_erros.py`: Handles error reporting for tag extraction and validation.

5. **Documentation**
   - `README.md`: Project overview and usage instructions.
   - `design_doc.md`: Detailed design and architecture (this document).

### Data Flow

1. **Ingestion**
   - User runs an ingestion script (e.g., `ingest.py`).
   - Script parses log files, extracts relevant data, and inserts into SQLite tables.
   - Schema validation ensures data integrity.

2. **Analysis/Peek**
   - User runs a peek/query script (e.g., `peek.py`).
   - Script queries the database for requested information (files, tags, totals).
   - Results are displayed via CLI or can be exported.

3. **Validation**
   - Schema and tag validation scripts ensure data consistency and report errors.

## Key Modules

- `app.py`: Main application logic or entry point.
- `schema.py`: Defines database schema.
- `check_schema.py`: Validates schema integrity.
- `ingest.py`, `ingest_files.py`, `ingest_headers.py`, `ingest_totals.py`: Ingestion scripts.
- `peek.py`, `peek_files.py`, `peek_tags.py`, `peek_totals.py`: Query/peek scripts.
- `tag_erros.py`: Error handling for tags.
- `requirements.txt`: Python dependencies.

## Extensibility

- **New Log Formats**: Add new ingestion scripts or extend existing ones to support additional formats.
- **Custom Analysis**: Add new peek/query scripts for specialized analysis.
- **Schema Evolution**: Update `schema.py` and `check_schema.py` to support schema changes.

## Error Handling

- Centralized in `tag_erros.py` and validation scripts.
- Ensures robust reporting and handling of malformed data or schema mismatches.

## Usage

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Ingest logs**:
   ```bash
   python ingest.py <log_file>
   ```
3. **Validate schema**:
   ```bash
   python check_schema.py
   ```
4. **Peek/query data**:
   ```bash
   python peek.py --tags
   python peek.py --totals
   ```

## Future Improvements

- Add support for more database backends (e.g., PostgreSQL).
- Implement a web-based dashboard for visualization.
- Add unit and integration tests for all modules.
- Enhance error handling and reporting.
- Support for real-time log ingestion and analysis.

## Conclusion

Devlog Analyzer is designed for modular, extensible, and reliable analysis of development logs. Its architecture supports easy ingestion, validation, and querying, making it a valuable tool for developers seeking insights from their devlogs.
