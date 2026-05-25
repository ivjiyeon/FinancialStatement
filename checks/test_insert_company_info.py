
import sqlite3
import os
import sys
import logging
import pandas as pd

# Add the directory containing dart package to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'projects/financial_statement'))

from dart.util import init_db, insert_financial_data, get_db_connection # Import get_db_connection

DB_PATH = "./temp_dart_insert_test.db"

def setup_logging():
    logging.basicConfig(level=logging.DEBUG, # Set to DEBUG for more verbosity
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    if not logging.getLogger().handlers:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

def test_insert_company_info():
    setup_logging()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    logging.info(f"Initializing database at {DB_PATH}...")
    init_db(DB_PATH)
    logging.info("Database initialized.")

    # Create a dummy DataFrame for company_info
    dummy_company_info_data = [
        {'corp_code': '00126380', 'corp_name': '삼성전자', 'stock_code': '005930', 'modify_date': '20230101'},
        {'corp_code': '00164742', 'corp_name': '카카오', 'stock_code': '035720', 'modify_date': '20230101'},
        {'corp_code': '00126380', 'corp_name': '삼성전자(수정)', 'stock_code': '005930', 'modify_date': '20230102'}, # Duplicate corp_code to test ON CONFLICT
        {'corp_code': None, 'corp_name': 'Null Corp', 'stock_code': '999999', 'modify_date': '20230103'} # Null corp_code
    ]
    dummy_df = pd.DataFrame(dummy_company_info_data)

    logging.info(f"Attempting to insert {len(dummy_df)} dummy company_info records...")
    
    conn = None
    try:
        conn = get_db_connection(DB_PATH)
        insert_financial_data(conn, dummy_df, 'company_info')
        logging.info("insert_financial_data call completed.")

        # Check data count
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM company_info")
        count = cursor.fetchone()[0]
        logging.info(f"Number of records in company_info after insertion: {count}")

        # Verify data content after insertion (especially the update)
        cursor.execute("SELECT * FROM company_info")
        all_info = cursor.fetchall()
        logging.info(f"All company_info records: {all_info}")

        cursor.execute("SELECT * FROM company_info WHERE corp_code = '00126380'")
        samsung_info = cursor.fetchone()
        logging.info(f"Samsung Electronics info after update: {samsung_info}")

    except sqlite3.Error as e:
        logging.error(f"Database error during insertion test: {e}")
    finally:
        if conn:
            conn.close()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

if __name__ == "__main__":
    test_insert_company_info()
