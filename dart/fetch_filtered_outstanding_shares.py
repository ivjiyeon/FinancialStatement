import os
import pandas as pd
import logging
from dotenv import load_dotenv
from util import get_db_connection, insert_financial_data, _get_reporting_period_end_date # Removed fetch_outstanding_shares
import json
import subprocess # Added
def main():
    # Load environment variables from .env file
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))

    # Get KRX credentials
    krx_id = os.getenv('KRX_ID')
    krx_pw = os.getenv('KRX_PW')

    if not krx_id or not krx_pw:
        logging.error("KRX_ID or KRX_PW not found in environment variables. Please set them in the .env file.")
        return # Exit if credentials are not found

    # --- Configuration ---
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
    KRX_SCRIPT_PATH = os.path.join(PROJECT_ROOT, 'krx_sector', 'get_outstanding_shares_krx.py') # Added
    VENV_KRX_PATH = os.path.join(PROJECT_ROOT, 'venv_krx') # Added

    DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
    LOG_FILE = os.path.join(SCRIPT_DIR, 'fetch_filtered_outstanding_shares.log')
    TEMP_INPUT_JSON = os.path.join(PROJECT_ROOT, 'temp_outstanding_shares_input.json') # Added
    TEMP_OUTPUT_JSON = os.path.join(PROJECT_ROOT, 'temp_outstanding_shares_output.json') # Added

    # --- Logging Setup ---
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

    logging.info("Script started: Fetching outstanding shares for filtered companies.")
    logging.info(f"Database path: {DB_PATH}")

    # --- Target Period (consistent with analyze_and_identify_undervalued.py) ---
    TARGET_BSNS_YEAR = 2025
    TARGET_REPRT_CODE = '11011' # Q4/Annual report

    # Calculate the target trade date string for pykrx
    target_trade_date_for_pykrx = _get_reporting_period_end_date(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)
    logging.info(f"Target trade date for pykrx (derived from report code): {target_trade_date_for_pykrx}")

    # --- Corp Codes of 18 Filtered Companies (from previous successful run) ---
    filtered_corp_codes = [
        '00106641', '00111874', '00125521', '00126380', '00139834', '00140964',
        '00158501', '00160843', '00165060', '00182696', '00306719', '00360595',
        '00361381', '00425351', '00776820', '01108099', '01596425', '01806951'
    ]

    # --- Load company info from DB to get stock_code ---
    company_info_map = {}
    try:
        with get_db_connection(DB_PATH) as conn:
            company_info_df = pd.read_sql_query("SELECT corp_code, stock_code, corp_name FROM company_info", conn)
            for _, row in company_info_df.iterrows():
                company_info_map[row['corp_code']] = {'stock_code': row['stock_code'], 'corp_name': row['corp_name']}
            logging.info(f"Loaded {len(company_info_df)} company_info records from DB.")
    except Exception as e:
        logging.error(f"Error loading company_info from DB: {e}")
        return

    # --- Fetch and store outstanding shares ---
    companies_to_fetch = []
    for corp_code in filtered_corp_codes:
        info = company_info_map.get(corp_code)
        if not info or not info['stock_code']:
            logging.warning(f"Skipping {corp_code}: Stock code not found in company_info.")
            continue
        
        companies_to_fetch.append({
            'corp_code': corp_code,
            'stock_code': info['stock_code'],
            'bsns_year': TARGET_BSNS_YEAR,
            'reprt_code': TARGET_REPRT_CODE,
            'trade_date_str': target_trade_date_for_pykrx # Pass the calculated date
        })

    if not companies_to_fetch:
        logging.warning("No companies to fetch outstanding shares for.")
        return

    logging.info(f"Preparing to fetch outstanding shares for {len(companies_to_fetch)} companies using KRX script.")
    
    try:
        with open(TEMP_INPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(companies_to_fetch, f, ensure_ascii=False, indent=4)
        logging.info(f"Wrote input JSON for KRX script to: {TEMP_INPUT_JSON}")

        command = [
            os.path.join(VENV_KRX_PATH, 'bin', 'python3'),
            KRX_SCRIPT_PATH,
            TEMP_INPUT_JSON,
            TEMP_OUTPUT_JSON
        ]
        # full_command is now a list, not a string

        logging.info(f"Executing KRX script in venv_krx: {' '.join(command)}")
        # Prepare environment variables for the subprocess
        # Copy current environment and add/override KRX credentials
        subprocess_env = os.environ.copy()
        subprocess_env['KRX_ID'] = krx_id
        subprocess_env['KRX_PW'] = krx_pw

        # Use subprocess.run for better error handling and blocking execution
        result = subprocess.run(command, capture_output=True, text=True, check=True, env=subprocess_env) # Removed shell=True, executable=/bin/bash
        logging.info(f"KRX script stdout:\n{result.stdout}")
        if result.stderr:
            logging.error(f"KRX script stderr:\n{result.stderr}")

        logging.info(f"Reading results from output JSON: {TEMP_OUTPUT_JSON}")
        with open(TEMP_OUTPUT_JSON, 'r', encoding='utf-8') as f:
            krx_results = json.load(f)
        
        if krx_results:
            outstanding_shares_df = pd.DataFrame(krx_results)
            with get_db_connection(DB_PATH) as conn:
                insert_financial_data(conn, outstanding_shares_df, 'outstanding_shares')
            logging.info(f"Successfully inserted {len(outstanding_shares_df)} outstanding shares records from KRX script.")
        else:
            logging.warning("No outstanding shares data returned by KRX script.")

    except subprocess.CalledProcessError as e:
        logging.error(f"KRX script failed with error: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")
    except Exception as e:
        logging.error(f"An error occurred during KRX outstanding shares processing: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists(TEMP_INPUT_JSON):
            os.remove(TEMP_INPUT_JSON)
            logging.info(f"Removed temporary input JSON: {TEMP_INPUT_JSON}")
        if os.path.exists(TEMP_OUTPUT_JSON):
            os.remove(TEMP_OUTPUT_JSON)
            logging.info(f"Removed temporary output JSON: {TEMP_OUTPUT_JSON}")

    logging.info("Script finished: Filtered outstanding shares processed.")

if __name__ == "__main__":
    main()