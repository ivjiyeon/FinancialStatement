
import sqlite3
import os
import sys
import logging
import pandas as pd # Required by get_corp_codes for DataFrame operations

# Add the directory containing dart package to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'projects/financial_statement'))

from dart.util import init_db, get_corp_codes

DB_PATH = "./temp_dart_data.db"
DUMMY_API_KEY = "DUMMY_KEY_FOR_TESTING" # This won't fetch real data, but will allow execution

def setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    # Prevent duplicate log messages if this function is called multiple times
    if not logging.getLogger().handlers:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

def check_company_info_count():
    setup_logging()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    logging.info(f"Initializing database at {DB_PATH}...")
    init_db(DB_PATH)
    logging.info("Database initialized.")

    # Call get_corp_codes
    logging.info("Calling get_corp_codes to populate company_info...")
    # get_corp_codes expects an API key, but for this test, a dummy one is fine
    # as we're testing the DB interaction, not actual API fetching.
    get_corp_codes(DUMMY_API_KEY, DB_PATH)
    logging.info("get_corp_codes call completed.")

    # Check data count
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM company_info")
        count = cursor.fetchone()[0]
        logging.info(f"Number of records in company_info after get_corp_codes: {count}")

    except sqlite3.Error as e:
        logging.error(f"Database error during count check: {e}")
    finally:
        if conn:
            conn.close()
        # Clean up the temporary database file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

if __name__ == "__main__":
    check_company_info_count()
