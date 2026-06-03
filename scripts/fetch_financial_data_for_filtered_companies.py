import sqlite3
import pandas as pd
import os
import logging
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_ROOT = Path('/home/ivjiyeonb/projects/financial_statement/')
DB_PATH = PROJECT_ROOT / 'data' / 'financial_data.db'
VENV_KRX_PYTHON = PROJECT_ROOT / 'venv_krx' / 'bin' / 'python'
VENV_DART_PYTHON = PROJECT_ROOT / 'venv_dart' / 'bin' / 'python'

def _get_db_connection():
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(str(DB_PATH))

def get_filtered_companies(bsns_year, reprt_code):
    logging.info(f"Fetching filtered companies for {bsns_year}-{reprt_code} from database (raw SQL)...")
    companies = []
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT fc.corp_code, ci.stock_code, fc.bsns_year, fc.reprt_code
                FROM filtered_companies AS fc
                JOIN company_info AS ci ON fc.corp_code = ci.corp_code
                WHERE fc.bsns_year = ? AND fc.reprt_code = ?
            """
            cursor.execute(query, (bsns_year, reprt_code))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            for row in rows:
                companies.append(dict(zip(columns, row)))
        logging.info(f"Found {len(companies)} filtered companies (raw SQL).")
    except Exception as e:
        logging.error(f"Error fetching filtered companies (raw SQL): {e}")
    return companies

def init_new_tables():
    """
    Initializes the new tables for stock prices and outstanding shares data.
    """
    logging.info("Initializing new database tables: stock_prices_data and outstanding_shares_data...")
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            # Drop tables if they exist to ensure a clean start
            cursor.execute('DROP TABLE IF EXISTS stock_prices_data;')
            cursor.execute('DROP TABLE IF EXISTS outstanding_shares_data;')

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
                    stock_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    outstanding_shares INTEGER,
                    PRIMARY KEY (corp_code, stock_code, trade_date)
                )
            ''')
            conn.commit()
        logging.info("New tables initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing new tables: {e}")

def run_krx_data_fetch_script(corp_code: str, stock_code: str, start_date: str, end_date: str, krx_id: str, krx_pw: str) -> bool:
    """
    Executes a separate Python script within venv_krx to fetch KRX data.
    """
    script_path = PROJECT_ROOT / 'scripts' / 'krx_data_fetch_worker.py'

    if not os.path.exists(script_path):
        logging.error(f"Krx data fetch worker script not found at {script_path}. Cannot proceed.")
        return False

    command = [
        str(VENV_KRX_PYTHON),
        str(script_path),
        '--corp_code', corp_code,
        '--stock_code', stock_code,
        '--start_date', start_date,
        '--end_date', end_date,
        '--db_path', str(DB_PATH)
    ]
    #logging.info(f"Executing KRX data fetch for {stock_code} ({corp_code}) from {start_date} to {end_date}...")
    
    subprocess_env = os.environ.copy()
    subprocess_env['KRX_ID'] = krx_id
    subprocess_env['KRX_PW'] = krx_pw

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=subprocess_env)
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

def run_dart_data_fetch_script(corp_code: str, stock_code: str, bsns_year: int, reprt_code: str, db_path: Path, dart_api_key: str) -> bool:
    """
    Executes a separate Python script within venv_dart to fetch DART outstanding shares data.
    """
    script_path = PROJECT_ROOT / 'scripts' / 'dart_data_fetch_worker.py'

    if not os.path.exists(script_path):
        logging.error(f"DART data fetch worker script not found at {script_path}. Cannot proceed.")
        return False

    command = [
        str(VENV_DART_PYTHON),
        str(script_path),
        '--corp_code', corp_code,
        '--stock_code', stock_code,
        '--bsns_year', str(bsns_year),
        '--reprt_code', reprt_code,
        '--db_path', str(db_path)
    ]
    #logging.info(f"Executing DART data fetch for {stock_code} (Corp Code: {corp_code}, Year: {bsns_year}) using DART API...")

    subprocess_env = os.environ.copy()
    subprocess_env['DART_API_KEY'] = dart_api_key

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=subprocess_env)
        logging.info(f"DART data fetch for {stock_code} completed. Output:\n{result.stdout}")
        if result.stderr:
            logging.warning(f"DART data fetch for {stock_code} stderr:\n{result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"DART data fetch for {stock_code} failed with error:\n{e.stderr}\n{e.stdout}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during DART data fetch for {stock_code}: {e}")
        return False

def main():
    # --- Configuration for data fetching ---
    current_date = datetime.now()
    
    load_dotenv() # Load .env file
    KRX_ID = os.getenv('KRX_ID')
    KRX_PW = os.getenv('KRX_PW')
    DART_API_KEY = os.getenv('DART_API_KEY') # Load DART API key
    TARGET_BSNS_YEAR = os.getenv('TARGET_BSNS_YEAR')
    TARGET_REPRT_CODE = os.getenv('TARGET_REPRT_CODE')

    if not KRX_ID or not KRX_PW:
        logging.error("KRX_ID or KRX_PW environment variables are not set. Please set them in the .env file or ensure it's loaded.")
        return
    logging.info(f"KRX_ID set: {bool(KRX_ID)}")

    if not DART_API_KEY:
        logging.error("DART_API_KEY environment variable is not set. Please set it in the .env file or ensure it's loaded.")
        return
    logging.info(f"DART_API_KEY set: {bool(DART_API_KEY)}")

    init_new_tables()
    
    filtered_companies_list = get_filtered_companies(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

    if not filtered_companies_list:
        logging.info("No filtered companies found to fetch data for.")
        return

    logging.info(f"Fetching data for {len(filtered_companies_list)} companies...")
    for company_data in filtered_companies_list:
        corp_code = company_data['corp_code']
        stock_code = company_data['stock_code']
        bsns_year = company_data['bsns_year']
        reprt_code = company_data['reprt_code']

        logging.info(f"Processing {stock_code} (Corp Code: {corp_code})...")
        start_date_krx = (current_date - timedelta(days=7)).strftime('%Y%m%d')
        end_date_krx = current_date.strftime('%Y%m%d')
        # Fetch KRX stock prices (OHLCV) - using calculated start and end dates
        run_krx_data_fetch_script(corp_code, stock_code, start_date_krx, end_date_krx, KRX_ID, KRX_PW)
        
        # Fetch DART outstanding shares - without trade_date
        run_dart_data_fetch_script(corp_code, stock_code, bsns_year, reprt_code, DB_PATH, DART_API_KEY)
    
    logging.info("Finished fetching financial data for filtered companies.")

if __name__ == "__main__":
    main()
