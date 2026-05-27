import sqlite3
import pandas as pd
import os
import logging
import subprocess
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_ROOT = '/home/ivjiyeonb/projects/financial_statement/'
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'financial_data.db')
VENV_KRX_PYTHON = os.path.join(PROJECT_ROOT, 'venv_krx', 'bin', 'python')

def _get_db_connection():
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def get_filtered_companies(bsns_year, reprt_code):
    """
    Retrieves the list of filtered company corp_codes from the database.
    """
    logging.info(f"Fetching filtered companies for {bsns_year}-{reprt_code} from database...")
    filtered_companies_df = pd.DataFrame()
    try:
        with _get_db_connection() as conn:
            query = f"""
                SELECT DISTINCT fc.corp_code, ci.stock_code, fc.bsns_year, fc.reprt_code
                FROM filtered_companies AS fc
                JOIN company_info AS ci ON fc.corp_code = ci.corp_code
                WHERE fc.bsns_year = ? AND fc.reprt_code = ?
            """
            filtered_companies_df = pd.read_sql_query(query, conn, params=(bsns_year, reprt_code), dtype={
                'corp_code': str,
                'stock_code': str,
                'bsns_year': 'int16',
                'reprt_code': str
            })
        logging.info(f"Found {len(filtered_companies_df)} filtered companies.")
    except Exception as e:
        logging.error(f"Error fetching filtered companies: {e}")
    return filtered_companies_df

def init_new_tables():
    """
    Initializes the new tables for stock prices and outstanding shares data.
    """
    logging.info("Initializing new database tables: stock_prices_data and outstanding_shares_data...")
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_prices_data (
                    stock_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open_price INTEGER,
                    high_price INTEGER,
                    low_price INTEGER,
                    close_price INTEGER,
                    volume INTEGER,
                    PRIMARY KEY (stock_code, trade_date)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS outstanding_shares_data (
                    corp_code TEXT NOT NULL,
                    bsns_year INTEGER NOT NULL,
                    reprt_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    outstanding_shares INTEGER,
                    PRIMARY KEY (corp_code, bsns_year, reprt_code, trade_date)
                )
            ''')
            conn.commit()
        logging.info("New tables initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing new tables: {e}")

def run_krx_data_fetch_script(corp_code, stock_code, bsns_year, reprt_code, start_date, end_date):
    """
    Executes a separate Python script within venv_krx to fetch KRX data.
    """
    script_path = os.path.join(PROJECT_ROOT, 'scripts', 'krx_data_fetch_worker.py')
    
    # Ensure the worker script exists
    if not os.path.exists(script_path):
        logging.error(f"Krx data fetch worker script not found at {script_path}. Cannot proceed.")
        return False

    command = [
        VENV_KRX_PYTHON,
        script_path,
        '--corp_code', corp_code,
        '--stock_code', stock_code,
        '--bsns_year', str(bsns_year),
        '--reprt_code', reprt_code,
        '--start_date', start_date,
        '--end_date', end_date,
        '--db_path', DB_PATH
    ]
    logging.info(f"Executing KRX data fetch for {stock_code} ({corp_code}) from {start_date} to {end_date}...")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.info(f"Krx data fetch for {stock_code} completed. Output:\n{result.stdout}")
        if result.stderr:
            logging.warning(f"Krx data fetch for {stock_code} stderr:\n{result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Krx data fetch for {stock_code} failed with error:\n{e.stderr}\n{e.stdout}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during KRX data fetch for {stock_code}: {e}")
        return False

def main():
    # --- Configuration for data fetching ---
    # These should be consistent with analyze_and_identify_undervalued.py
    TARGET_BSNS_YEAR = 2025
    TARGET_REPRT_CODE = '11011' # 11013 for Q3, 11012 for Q2, 11011 for Q4 (Annual), 11014 for Q1

    init_new_tables()
    
    filtered_companies_df = get_filtered_companies(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

    if filtered_companies_df.empty:
        logging.info("No filtered companies found to fetch KRX data for.")
        return

    # Determine date range for fetching stock prices
    # For simplicity, let's fetch for the last 30 days up to today.
    # In a real scenario, this might be more sophisticated (e.g., historical prices around report dates).
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    logging.info(f"Fetching KRX data for {len(filtered_companies_df)} companies from {start_date} to {end_date}...")
    for index, row in filtered_companies_df.iterrows():
        corp_code = row['corp_code']
        stock_code = row['stock_code']
        bsns_year = row['bsns_year']
        reprt_code = row['reprt_code']

        logging.info(f"Processing {row['stock_code']} (Corp Code: {row['corp_code']})...")
        run_krx_data_fetch_script(corp_code, stock_code, bsns_year, reprt_code, start_date, end_date)
    
    logging.info("Finished fetching financial data for filtered companies.")

if __name__ == "__main__":
    main()
