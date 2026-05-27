import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pykrx.stock import get_market_ohlcv_by_ticker, get_market_fundamental_by_ticker, get_previous_business_days
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_outstanding_shares_pykrx(stock_code, trade_date_str):
    """
    Fetches outstanding shares for a given stock_code and date using pykrx.
    Calculates outstanding shares from market cap and close price.
    Tries the given date and a few preceding business days if no data.
    """
    # Try the given date and then a few preceding business days if no data
    for i in range(5): # Try up to 5 previous business days
        current_attempt_date = (datetime.strptime(trade_date_str, '%Y%m%d') - timedelta(days=i)).strftime('%Y%m%d')
        
        try:
            # 1. Fetch Close Price (종가)
            df_ohlcv = get_market_ohlcv_by_ticker(current_attempt_date, stock_code)
            if df_ohlcv.empty or '종가' not in df_ohlcv.columns:
                logging.debug(f"No OHLCV data (or '종가' column missing) for {stock_attempt_date} on {current_attempt_date}. Trying previous day.")
                continue # Try previous day
            close_price = df_ohlcv['종가'].iloc[0]

            # 2. Fetch Fundamental Data (시가총액)
            df_fundamental = get_market_fundamental_by_ticker(current_attempt_date, stock_code)
            if df_fundamental.empty or '시가총액' not in df_fundamental.columns:
                logging.debug(f"No fundamental data (or '시가총액' column missing) for {stock_code} on {current_attempt_date}. Trying previous day.")
                continue # Try previous day

            market_cap = df_fundamental['시가총액'].iloc[0]

            if close_price > 0:
                outstanding_shares = int(market_cap / close_price)
                logging.info(f"Calculated outstanding shares for {stock_code} on {current_attempt_date}: {outstanding_shares} (Original target date: {trade_date_str})")
                return outstanding_shares
            else:
                logging.warning(f"Close price for {stock_code} on {current_attempt_date} is zero or negative. Cannot calculate outstanding shares. Trying previous day.")
                continue # Try previous day

        except Exception as e:
            logging.warning(f"Error fetching/calculating outstanding shares for {stock_code} on {current_attempt_date}: {e}. Trying previous day.")
            continue # Try previous day

    logging.error(f"Failed to fetch outstanding shares for {stock_code} around {trade_date_str} after multiple attempts.")
    return None

def main():
    # Load environment variables (for KRX_ID/PW if pykrx requires them internally)
    # This script will be run from project root context, so .env is there.
    load_dotenv() 

    if len(sys.argv) != 3:
        logging.error("Usage: python get_outstanding_shares_krx.py <input_json_path> <output_json_path>")
        sys.exit(1)

    input_json_path = sys.argv[1]
    output_json_path = sys.argv[2]
    
    logging.info(f"Reading stock codes from: {input_json_path}")
    try:
        with open(input_json_path, 'r', encoding='utf-8') as f:
            companies_to_fetch = json.load(f)
    except Exception as e:
        logging.error(f"Error reading input JSON file {input_json_path}: {e}")
        sys.exit(1)

    results = []
    for item in companies_to_fetch:
        corp_code = item['corp_code']
        stock_code = item['stock_code']
        bsns_year = item['bsns_year']
        reprt_code = item['reprt_code']
        target_trade_date_str = item['trade_date_str'] # Expect trade_date_str in input

        outstanding_shares = get_outstanding_shares_pykrx(stock_code, target_trade_date_str)
        
        if outstanding_shares is not None:
            results.append({
                'corp_code': corp_code,
                'bsns_year': bsns_year,
                'reprt_code': reprt_code,
                'outstanding_shares': outstanding_shares,
                'fetched_on_date': target_trade_date_str # Record the date the shares were fetched for
            })

    logging.info(f"Writing results to: {output_json_path}")
    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error writing output JSON file {output_json_path}: {e}")
        sys.exit(1)
    
    logging.info("Finished fetching outstanding shares via pykrx.")

if __name__ == "__main__":
    main()