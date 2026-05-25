
import sqlite3
import os
import sys

# Add the directory containing util.py to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'projects/financial_statement'))

from dart.util import init_db

DB_PATH = "./temp_dart_test.db"

def check_company_info_schema():
    # Ensure a clean slate for the database for testing purposes
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print(f"Initializing database at {DB_PATH}...")
    init_db(DB_PATH)
    print("Database initialized.")

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Checking schema for company_info table...")
        cursor.execute("PRAGMA table_info(company_info)")
        schema = cursor.fetchall()

        if schema:
            print("\nSchema for company_info:")
            for col in schema:
                print(col) # (cid, name, type, notnull, dflt_value, pk)
            
            # Verify corp_code is PRIMARY KEY
            corp_code_pk = False
            for col in schema:
                if col[1] == 'corp_code' and col[5] == 1: # col[1] is name, col[5] is pk
                    corp_code_pk = True
                    break
            
            if corp_code_pk:
                print("\nVerification: 'corp_code' is indeed a PRIMARY KEY.")
            else:
                print("\nVerification: ERROR - 'corp_code' is NOT a PRIMARY KEY.")
        else:
            print("ERROR: company_info table not found or no schema information.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()
        # Clean up the temporary database file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

if __name__ == "__main__":
    check_company_info_schema()
