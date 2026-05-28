import argparse
import sqlite3
import os
import logging
import requests
from datetime import datetime
import json
import re
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DART_API_OUTSTANDING_SHARES_URL = "https://opendart.fss.or.kr/api/stockTotqySttus.json"
def _get_db_connection(db_path):
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(db_path)

def clean_amount(amount_str):
    """Removes commas and converts string to integer, handling empty/None."""
    if amount_str is None or amount_str == '':
        return 0
    # Use regex to remove all non-digit characters except for a leading minus sign
    # This assumes the input could be like '-1,234' or '1,234'
    clean_str = re.sub(r'[^\d-]', '', str(amount_str))
    return int(clean_str) if clean_str and clean_str != '-' else 0

def fetch_and_store_dart_outstanding_shares(db_path: Path, corp_code: str, stock_code: str, bsns_year: int, reprt_code: str, dart_api_key: str):
    logging.info(f"Fetching outstanding shares for {corp_code} (stock_code: {stock_code}, bsns_year: {bsns_year}, reprt_code: {reprt_code}) from DART API (stockTotqySttus.json)...")
    
    url = DART_API_OUTSTANDING_SHARES_URL
    params = {
        'crtfc_key': dart_api_key,
        'corp_code': corp_code,
        'bsns_year': str(bsns_year),
        'reprt_code': reprt_code,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors
        data = response.json()

        if data.get('status') != '000':
            logging.warning(f"DART API error for {corp_code} ({bsns_year}-{reprt_code}) (stockTotqySttus.json): {data.get('message', 'Unknown error')}. Skipping.")
            return
        
        items = data.get('list', [])
        if not items:
            logging.warning(f"No stock issuance status data found for {corp_code} ({bsns_year}-{reprt_code}) in stockTotqySttus.json. Skipping.")
            return
        
        # Process items to find the relevant outstanding shares
        common_outstanding_shares = 0
        trade_date = None

        # Collect trade_date from any item, preferably the latest or first valid one
        if items and 'rcept_dt' in items[0]:
            trade_date = items[0]['rcept_dt']
        else:
            trade_date = datetime.now().strftime('%Y%m%d') # Fallback if rcept_dt is missing

        for item in items:
            # Financial analyst recommended using common stock (보통주) for ratio calculations.
            if item.get('se') in ['보통주', '보통주식'] and 'istc_totqy' in item:
                common_outstanding_shares = clean_amount(item['istc_totqy'])
                break # Found common stock, no need to process further
        
        if common_outstanding_shares > 0:
            with _get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO outstanding_shares_data (corp_code, stock_code, trade_date, outstanding_shares)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(corp_code, stock_code, trade_date) DO UPDATE SET
                        outstanding_shares = excluded.outstanding_shares
                ''', (corp_code, stock_code, trade_date, common_outstanding_shares))
                conn.commit()
            logging.info(f"Successfully stored DART outstanding shares for {corp_code} (stock_code: {stock_code}, shares: {common_outstanding_shares}) from stockTotqySttus.json.")
        else:
            logging.warning(f"No valid common outstanding shares found or calculated for {corp_code} from stockTotqySttus.json. Skipping storage.")

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP Request error fetching DART data for {corp_code}: {e}")
    except json.JSONDecodeError:
        logging.error(f"JSON Decode error for DART data for {corp_code}: Invalid response.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during DART data fetch for {corp_code}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Fetch DART outstanding shares data and store in DB.')
    parser.add_argument('--corp_code', type=str, required=True, help='Corporate code')
    parser.add_argument('--stock_code', type=str, required=True, help='Stock code')
    parser.add_argument('--bsns_year', type=int, required=True, help='Business year (e.g., 2023)')
    parser.add_argument('--reprt_code', type=str, required=True, help='Report code (e.g., 11011 for Annual)')
    parser.add_argument('--db_path', type=str, required=True, help='Path to the SQLite database')

    args = parser.parse_args()

    db_path = Path(args.db_path)

    DART_API_KEY = os.getenv('DART_API_KEY')
    if not DART_API_KEY:
        logging.error("DART_API_KEY environment variable is not set. Please set it.")
        return

    fetch_and_store_dart_outstanding_shares(db_path, args.corp_code, args.stock_code, args.bsns_year, args.reprt_code, DART_API_KEY)

if __name__ == '__main__':
    main()