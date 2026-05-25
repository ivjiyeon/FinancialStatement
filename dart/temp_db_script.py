
import sqlite3
import os
import sys

# Add the project root to the Python path to import dart.util
sys.path.append('/home/ivjiyeonb/projects/financial_statement')

from dart.util import init_db

DATABASE_PATH = '/home/ivjiyeonb/projects/financial_statement/data/financial_data.db'

def main():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Drop the financial_statements table if it exists
        cursor.execute("DROP TABLE IF EXISTS financial_statements")
        conn.commit()
        print("Dropped 'financial_statements' table if it existed.")

        # Initialize the database (this should recreate financial_statements and preserve others)
        init_db(DATABASE_PATH)
        print("Database initialized using dart.util.init_db(). 'financial_statements' table refreshed.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
