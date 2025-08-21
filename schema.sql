-- MySQL Schema for DevLog Analyzer

-- Commits table
CREATE TABLE IF NOT EXISTS commits (
  hash VARCHAR(40) PRIMARY KEY,
  author_name VARCHAR(255) NOT NULL,
  author_email VARCHAR(255) NOT NULL,
  authored_at DATETIME NOT NULL,
  message TEXT NOT NULL,
  additions INT NOT NULL DEFAULT 0,
  deletions INT NOT NULL DEFAULT 0,
  files_changed INT NOT NULL DEFAULT 0,
  is_fix TINYINT NOT NULL DEFAULT 0,
  error_tags VARCHAR(255),
  INDEX idx_commits_date (authored_at),
  INDEX idx_commits_author (author_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Commit files table
CREATE TABLE IF NOT EXISTS commit_files (
  id INT AUTO_INCREMENT PRIMARY KEY,
  commit_hash VARCHAR(40) NOT NULL,
  file_path VARCHAR(255) NOT NULL,
  additions INT NOT NULL DEFAULT 0,
  deletions INT NOT NULL DEFAULT 0,
  UNIQUE KEY(commit_hash, file_path),
  INDEX idx_files_path (file_path),
  INDEX idx_files_commit (commit_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
