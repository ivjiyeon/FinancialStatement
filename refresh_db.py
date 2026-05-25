import sqlite3
import os
import sys

# Add the parent directory of dart to the Python path
# so we can import dart.util
sys.path.append(os.path.abspath('/home/ivjiyeonb/projects/financial_statement'))

from dart.util import init_db

DB_PATH = '/home/ivjiyeonb/projects/financial_statement/data/financial_data.db'

def refresh_financial_statements_table(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Drop financial_statements table if it exists
        print("Attempting to drop 'financial_statements' table if it exists...")
        cursor.execute("DROP TABLE IF EXISTS financial_statements;")
        conn.commit()
        print("'financial_statements' table dropped successfully (if it existed).")

        # Call init_db to re-create financial_statements and ensure company_info exists
        print("Calling init_db to initialize/re-create tables...")
        init_db(db_path)
        print("Database initialization complete.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    refresh_financial_statements_table(DB_PATH)
