import sqlite3
import logging
import datetime
import os
from config import config # Import the already loaded config

# Get the database file path from config, ensure directory exists
db_config = config.get('state_database', {})
DB_FILE = db_config.get('db_file', 'processed_articles.db') # Use default name if not in config

def _ensure_db_directory_exists():
    """Ensures the directory for the SQLite database file exists."""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            logging.info(f"Created directory for database: {db_dir}")
        except OSError as e:
            logging.error(f"Failed to create directory for database {db_dir}: {e}")
            raise

def initialize_db():
    """Initializes the SQLite database, creating the table if it doesn't exist."""
    _ensure_db_directory_exists()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_articles (
            url TEXT PRIMARY KEY,
            processed_at TIMESTAMP NOT NULL,
            status TEXT,          -- e.g., 'filtered', 'processed', 'pushed', 'failed_fetch', 'failed_ai', 'failed_push'
            title TEXT,           -- Store title for easier debugging
            filter_result TEXT    -- Store AI filter decision (optional)
        )''')
        conn.commit()
        logging.info(f"Database initialized successfully at {DB_FILE}")
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization at {DB_FILE}: {e}")
        raise # Propagate error if DB can't be initialized
    finally:
        if conn:
            conn.close()

def is_article_processed(url):
    """Checks if an article URL exists in the processed articles database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_articles WHERE url = ?", (url,))
        result = cursor.fetchone()
        return result is not None
    except sqlite3.Error as e:
        logging.error(f"Database error while checking URL {url}: {e}")
        return False # Assume not processed if DB error occurs
    finally:
        if conn:
            conn.close()

def mark_article_status(url, status, title="N/A", filter_result=None):
    """Marks an article URL with a specific status in the database. Inserts or updates."""
    conn = None
    timestamp = datetime.datetime.now().isoformat()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Use INSERT OR REPLACE (or ON CONFLICT UPDATE) to handle existing entries
        cursor.execute("""
        INSERT INTO processed_articles (url, processed_at, status, title, filter_result)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            processed_at = excluded.processed_at,
            status = excluded.status,
            title = excluded.title,
            filter_result = excluded.filter_result;
        """, (url, timestamp, status, title, filter_result))
        conn.commit()
        logging.debug(f"Marked article '{url}' with status '{status}'")
    except sqlite3.Error as e:
        logging.error(f"Database error marking status '{status}' for {url}: {e}")
    finally:
        if conn:
            conn.close()

# --- Optional: Functions to get stats or specific articles --- #

def get_processed_count():
    """Returns the total number of articles recorded in the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM processed_articles")
        count = cursor.fetchone()[0]
        return count
    except sqlite3.Error as e:
        logging.error(f"Database error retrieving processed count: {e}")
        return 0
    finally:
        if conn:
            conn.close()

# Ensure database is initialized on module load
initialize_db() 