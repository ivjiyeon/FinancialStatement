import os
import argparse
import pandas as pd
from datetime import datetime
import sqlite3
import time
import logging
from dotenv import load_dotenv

# Import refactored functions
from util import (
    _clean_financial_df,
    get_db_connection,
    insert_financial_data,
    get_corp_codes,
    fetch_financial_statements
)

def main():
    # Load environment variables from .env file
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))

    # --- Configuration ---
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

    DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
    CSV_PATH = os.path.join(DATA_DIR, 'krx_sector_data.csv')
    LOG_FILE = os.path.join(SCRIPT_DIR, 'fetch_initial_data.log')
    API_CALL_DELAY = 0.5

    # --- Logging Setup ---
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

    logging.info("Script started: Fetching initial historical financial statements.")
    logging.info(f"Database path: {DB_PATH}")
    logging.info(f"KRX Sector Data path: {CSV_PATH}")

    # --- Database Initialization ---
    from dart.util import init_db
    init_db(DB_PATH)

    parser = argparse.ArgumentParser(description="Fetch one year of historical financial statements using DART API.")
    parser.add_argument("--api_key", type=str, help="FSS DART API Key")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("DART_API_KEY")

    if not api_key:
        print("Error: DART API Key not provided. Use --api_key argument or set DART_API_KEY environment variable.")
        return

    # --- Update Corporate Codes ---
    #get_corp_codes(api_key, DB_PATH)

    # --- Load KRX Sector Data ---
    try:
        krx_data = pd.read_csv(CSV_PATH, dtype={'Stock Code': str})
        logging.info(f"Loaded {len(krx_data)} companies from {CSV_PATH}")
    except FileNotFoundError:
        logging.error(f"Error: {CSV_PATH} not found.")
        return
    except Exception as e:
        logging.error(f"Error loading KRX sector data: {e}")
        return

    # --- Load Company Info from DB ---
    company_info_df = pd.DataFrame()
    try:
        with get_db_connection(DB_PATH) as conn:
            company_info_df = pd.read_sql_query("SELECT corp_code, stock_code, corp_name FROM company_info", conn)
            logging.info(f"Loaded {len(company_info_df)} company_info records from DB.")
    except Exception as e:
        logging.warning(f"Could not load company_info from DB: {e}. Proceeding without it for initial mapping.")

    # --- Merge KRX data with company_info to get corp_code ---
    krx_data.rename(columns={'Stock Code': 'stock_code', 'Stock Name': 'corp_name'}, inplace=True)
    merged_companies = pd.merge(krx_data, company_info_df, on='stock_code', how='left', suffixes=('_krx', '_db'))
    merged_companies['corp_name'] = merged_companies['corp_name_krx'].fillna(merged_companies['corp_name_db'])
    merged_companies.drop(columns=['corp_name_krx', 'corp_name_db'], inplace=True)
    companies_to_process = merged_companies.dropna(subset=['corp_code']).copy()
    logging.info(f"Found {len(companies_to_process)} companies with mapped corp_codes to process.")

    companies_missing_corp_code = merged_companies[merged_companies['corp_code'].isna()]
    if not companies_missing_corp_code.empty:
        logging.warning(f"Skipping {len(companies_missing_corp_code)} companies due to missing corp_code. "
                        "These companies might not be in DART's company_info yet or stock_code mismatch.")

    # --- Determine historical reporting periods (last full year) ---
    current_year = datetime.now().year
    target_year = current_year - 1 # Fetch data for the previous calendar year

    # Report codes for Q1, Q2, Q3, Q4
    # 11013: 1분기보고서 (Q1)
    # 11012: 반기보고서 (Q2)
    # 11014: 3분기보고서 (Q3)
    # 11011: 사업보고서 (Q4/Annual)
    reporting_periods = [
        #(target_year, '11013', 'Q1'),
        #(target_year, '11012', 'Q2'),
        (target_year, '11014', 'Q3'),
        (target_year, '11011', 'Q4'),
        #(target_year, '11014', 'Q3'),
        #(target_year, '11012', 'Q2'),
        #(target_year, '11013', 'Q1')
    ]

    # --- Fetch Historical Financial Statements ---
    for bsns_year, reprt_code, display_quarter in reporting_periods:
        logging.info(f"--- Fetching {display_quarter} reports for year {bsns_year} ---")
        processed_count = 0
        for index, company in companies_to_process.iterrows():
            processed_count += 1
            if display_quarter == 'Q3' and processed_count < 1470:
                print(f"skipping {processed_count}")
                continue
            corp_code = company['corp_code']
            stock_code = company['stock_code']
            corp_name = company['corp_name']

            logging.info(f"Processing {processed_count}/{len(companies_to_process)}: {corp_name} ({stock_code}/{corp_code}) for {bsns_year} {display_quarter}")

            try:
                finstate_df = fetch_financial_statements(api_key, corp_code, bsns_year=bsns_year, reprt_code=reprt_code)

                if finstate_df is not None and not finstate_df.empty:
                    finstate_df = _clean_financial_df(finstate_df)
                    finstate_df['stock_code'] = stock_code


                    if 'sj_div' in finstate_df.columns:
                        with get_db_connection(DB_PATH) as conn:
                            insert_financial_data(conn, finstate_df, 'financial_statements')

                        logging.info(f"Successfully fetched and stored {display_quarter} financial statements for {corp_name} ({stock_code}).")
                    else:
                        logging.warning(f"'sj_div' column not found for {corp_name} ({stock_code}). Cannot separate financial statements.")
                else:
                    logging.info(f"No {display_quarter} financial statements found for {corp_name} ({stock_code}) for {bsns_year}.")

            except Exception as e:
                logging.error(f"Error fetching/storing financial statements for {corp_name} ({stock_code}) for {bsns_year} {display_quarter}: {e}")

            #processed_count += 1
            time.sleep(API_CALL_DELAY) # Rate limiting
    logging.info("Script finished: Initial historical financial statements processed.")


if __name__ == "__main__":
    main()
