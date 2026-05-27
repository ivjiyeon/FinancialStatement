import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_ROOT = '/home/ivjiyeonb/projects/financial_statement/'
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'financial_data.db')

def check_db():
    logging.info(f"Checking database at: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logging.info(f"Tables found: {tables}")

        if ('filtered_companies',) in tables:
            logging.info("Table 'filtered_companies' exists.")
            cursor.execute("SELECT count(*) FROM filtered_companies;")
            count = cursor.fetchone()[0]
            logging.info(f"Number of rows in filtered_companies: {count}")
            
            cursor.execute("SELECT corp_code, bsns_year, reprt_code FROM filtered_companies LIMIT 5;")
            sample_data = cursor.fetchall()
            logging.info(f"Sample data from filtered_companies: {sample_data}")
        else:
            logging.error("Table 'filtered_companies' does NOT exist.")

    except Exception as e:
        logging.error(f"An error occurred during DB check: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_db()