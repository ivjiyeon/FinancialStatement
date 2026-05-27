import os
import pandas as pd
import logging
from dotenv import load_dotenv
from util import get_db_connection, insert_financial_data, fetch_outstanding_shares

def main():
    # Load environment variables from .env file
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))

    # --- Configuration ---
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

    DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
    LOG_FILE = os.path.join(SCRIPT_DIR, 'fetch_outstanding_shares.log')

    # --- Logging Setup ---
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

    logging.info("Script started: Fetching outstanding shares.")
    logging.info(f"Database path: {DB_PATH}")

    api_key = os.getenv("DART_API_KEY")

    if not api_key:
        logging.error("Error: DART API Key not provided. Set DART_API_KEY environment variable.")
        return

    # --- Target Period (should be consistent with analyze_and_identify_undervalued.py) ---
    TARGET_BSNS_YEAR = 2025
    TARGET_REPRT_CODE = '11011' # Q4/Annual report

    # --- Load company info from DB ---
    company_info_df = pd.DataFrame()
    try:
        with get_db_connection(DB_PATH) as conn:
            company_info_df = pd.read_sql_query("SELECT corp_code, stock_code, corp_name FROM company_info", conn)
            logging.info(f"Loaded {len(company_info_df)} company_info records from DB.")
    except Exception as e:
        logging.error(f"Error loading company_info from DB: {e}")
        return

    # --- Fetch and store outstanding shares ---
    processed_count = 0
    for index, company in company_info_df.iterrows():
        processed_count += 1
        corp_code = company['corp_code']
        corp_name = company['corp_name']

        logging.info(f"Processing {processed_count}/{len(company_info_df)}: {corp_name} ({corp_code}) for {TARGET_BSNS_YEAR} {TARGET_REPRT_CODE}")

        try:
            outstanding_shares_df = fetch_outstanding_shares(api_key, corp_code, TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

            if outstanding_shares_df is not None and not outstanding_shares_df.empty:
                with get_db_connection(DB_PATH) as conn:
                    insert_financial_data(conn, outstanding_shares_df, 'outstanding_shares')
                logging.info(f"Successfully fetched and stored outstanding shares for {corp_name} ({corp_code}).")
            else:
                logging.info(f"No outstanding shares found (or dummy value returned) for {corp_name} ({corp_code}) for {TARGET_BSNS_YEAR} {TARGET_REPRT_CODE}.")

        except Exception as e:
            logging.error(f"Error fetching/storing outstanding shares for {corp_name} ({corp_code}): {e}")

    logging.info("Script finished: Outstanding shares processed.")

if __name__ == "__main__":
    main()