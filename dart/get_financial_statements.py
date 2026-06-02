import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import time
import logging
from dotenv import load_dotenv

# Import refactored functions
from dart.util import (
    _parse_xml_response,
    _parse_json_response,
    determine_recent_report_code_and_year,
    _clean_financial_df,
    get_db_connection,
    insert_financial_data,
    get_corp_codes,
    fetch_financial_statements,
    delete_old_financial_data
)


 
def main():
    # Load environment variables from .env file
    # Assuming .env is in the parent directory relative to the script
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))

    # --- Configuration ---
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

    DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
    CSV_PATH = os.path.join(DATA_DIR, 'krx_sector_data.csv')
    LOG_FILE = os.path.join(SCRIPT_DIR, 'get_financial_statements.log')
    # API call delay to respect rate limits (e.g., 0.5 seconds between calls)
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

    logging.info("Script started: Fetching financial statements.")
    logging.info(f"Database path: {DB_PATH}")
    logging.info(f"KRX Sector Data path: {CSV_PATH}")

    # --- Database Initialization ---
    from dart.util import init_db
    init_db(DB_PATH)
    


    parser = argparse.ArgumentParser(description="Fetch quarterly financial statements using DART API (JSON).")
    parser.add_argument("--api_key", type=str, help="FSS DART API Key")
    args = parser.parse_args()

    # Use argument if provided, otherwise get from environment variable
    api_key = args.api_key or os.getenv("DART_API_KEY")

    if not api_key:
        print("Error: DART API Key not provided. Use --api_key argument or set DART_API_KEY environment variable.")
        return

    # --- Update Corporate Codes ---
    # This ensures the company_info table in the DB is up-to-date
    get_corp_codes(api_key, DB_PATH)

    # --- Determine the most recent *completed* quarter dynamically ---
    current_date = datetime.now()
    logging.info(f"Raw current date (datetime.now()): {current_date}")

    report_year, report_quarter_code, display_quarter = determine_recent_report_code_and_year(current_date)


    logging.info(f"Determined Report Year: {report_year}, Display Quarter: {display_quarter}, Report Quarter Code: {report_quarter_code}")

    # --- Clean old financial data for the determined report period ---
    delete_old_financial_data(DB_PATH, report_year - 2, report_quarter_code)

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
    # Rename 'Stock Code' in krx_data to 'stock_code' for merging
    krx_data.rename(columns={'Stock Code': 'stock_code', 'Stock Name': 'corp_name'}, inplace=True)

    # Merge to link KRX stock codes with DART corp_codes
    # Use left merge to keep all KRX companies and try to find their corp_code
    merged_companies = pd.merge(krx_data, company_info_df, on='stock_code', how='left', suffixes=('_krx', '_db'))

    # Prioritize corp_name from KRX data if available, otherwise use from DB
    merged_companies['corp_name'] = merged_companies['corp_name_krx'].fillna(merged_companies['corp_name_db'])
    # Drop duplicate name columns
    merged_companies.drop(columns=['corp_name_krx', 'corp_name_db'], inplace=True)

    # Filter out companies without a corp_code for now
    companies_to_process = merged_companies.dropna(subset=['corp_code']).copy()
    logging.info(f"Found {len(companies_to_process)} companies with mapped corp_codes to process.")

    companies_missing_corp_code = merged_companies[merged_companies['corp_code'].isna()]
    if not companies_missing_corp_code.empty:
        logging.warning(f"Skipping {len(companies_missing_corp_code)} companies due to missing corp_code. "
                        "These companies might not be in DART's company_info yet or stock_code mismatch.")
        # Optionally, you might want to try to fetch corp_codes for these later.

    # --- Fetch Financial Statements ---
    processed_count = 0
    for index, company in companies_to_process.iterrows():
        processed_count += 1

        corp_code = company['corp_code']
        stock_code = company['stock_code']
        corp_name = company['corp_name']

        logging.info(f"Processing {processed_count}/{len(companies_to_process)}: {corp_name} ({stock_code}/{corp_code}) for {report_year} {display_quarter}")

        try:
            # Fetch financial statements
            finstate_df = fetch_financial_statements(api_key, corp_code, bsns_year=report_year, reprt_code=report_quarter_code)

            if finstate_df is not None and not finstate_df.empty:
                # Clean and convert data types
                finstate_df = _clean_financial_df(finstate_df)

                # Add stock_code to the DataFrame before saving
                finstate_df['stock_code'] = stock_code

                # Store the financial data in the new normalized schema
                with get_db_connection(DB_PATH) as conn:
                    insert_financial_data(conn, finstate_df, 'financial_statements')

                logging.info(f"Successfully fetched and stored financial statements for {corp_name} ({stock_code}).")
            else:
                logging.info(f"No financial statements found for {corp_name} ({stock_code}) for {report_year} {display_quarter}.")

        except Exception as e:
            logging.error(f"Error fetching/storing financial statements for {corp_name} ({stock_code}): {e}")

        #processed_count += 1
        time.sleep(API_CALL_DELAY) # Rate limiting

    logging.info("Script finished: All financial statements processed.")


if __name__ == "__main__":
    main()
