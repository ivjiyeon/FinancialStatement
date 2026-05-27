import sys
import os
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv # Added
from pykrx.stock import get_market_ohlcv_by_date

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
sys.path.append(PROJECT_ROOT) # Added to include project root in sys.path for module imports

from dart.util import get_db_connection, insert_financial_data

def main():
    # Load environment variables from .env file
    load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, '.env')) # Added

    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

    DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')
    LOG_FILE = os.path.join(SCRIPT_DIR, 'fetch_stock_prices.log')

    # --- Logging Setup ---
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

    logging.info("Script started: Fetching stock prices.")
    logging.info(f"Database path: {DB_PATH}")

    # --- Stock Codes of 18 Filtered Companies ---
    target_stock_codes = [
        '000270', '005710', '005850', '005930', '064400', '009970',
        '012750', '000990', '013030', '439260', '069510', '086280',
        '054950', '067280', '111770', '227840', '402340', '472850'
    ]

    # --- Determine the latest trading date ---
    today = datetime.now()
    trade_date_str = today.strftime('%Y%m%d') # YYYYMMDD format

    # --- Fetch and store stock prices ---
    stock_prices_data = []
    for stock_code in target_stock_codes:
        logging.info(f"Fetching stock price for {stock_code} on {trade_date_str}")
        try:
            # pykrx.stock.get_market_ohlcv_by_date returns a DataFrame
            df_ohlcv = get_market_ohlcv_by_date(fromdate=trade_date_str, todate=trade_date_str, ticker=stock_code)
            
            if not df_ohlcv.empty:
                close_price = df_ohlcv['종가'].iloc[0] # 종가 is closing price
                stock_prices_data.append({
                    'stock_code': stock_code,
                    'trade_date': trade_date_str,
                    'close_price': close_price
                })
                logging.info(f"Successfully fetched {stock_code} - Close Price: {close_price}")
            else:
                logging.warning(f"No stock price data found for {stock_code} on {trade_date_str}.")

        except Exception as e:
            logging.error(f"Error fetching stock price for {stock_code} on {trade_date_str}: {e}")
    
    if stock_prices_data:
        stock_prices_df = pd.DataFrame(stock_prices_data)
        with get_db_connection(DB_PATH) as conn:
            insert_financial_data(conn, stock_prices_df, 'stock_prices')
        logging.info(f"Successfully inserted {len(stock_prices_df)} stock prices into stock_prices table.")
    else:
        logging.warning("No stock prices were fetched to insert.")

    logging.info("Script finished: Stock prices processed.")

if __name__ == "__main__":
    main()