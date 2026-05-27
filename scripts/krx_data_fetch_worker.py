import argparse
import sqlite3
import pandas as pd
from pykrx import stock
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _get_db_connection(db_path):
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(db_path)

def fetch_and_store_stock_prices(db_path, stock_code, start_date, end_date):
    logging.info(f"Fetching stock prices for {stock_code} from {start_date} to {end_date}...")
    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, stock_code)
        if df.empty:
            logging.warning(f"No stock price data found for {stock_code} from {start_date} to {end_date}.")
            return
        
        df = df.reset_index()
        df.columns = ['trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume', 'trading_value', 'change_rate']
        df['stock_code'] = stock_code
        df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')

        # Select relevant columns for storage
        df_to_store = df[['stock_code', 'trade_date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']]

        with _get_db_connection(db_path) as conn:
            df_to_store.to_sql('stock_prices_data', conn, if_exists='append', index=False)
        logging.info(f"Successfully stored stock prices for {stock_code}.")
    except Exception as e:
        logging.error(f"Error fetching/storing stock prices for {stock_code}: {e}")

def fetch_and_store_outstanding_shares(db_path, corp_code, bsns_year, reprt_code, start_date, end_date):
    logging.info(f"Fetching outstanding shares for {corp_code} ({bsns_year}-{reprt_code}) from {start_date} to {end_date}...")
    try:
        # pykrx get_market_cap_by_date provides market cap, shares, etc.
        # We need to extract outstanding shares from it.
        df_cap = stock.get_market_cap_by_date(start_date, end_date, corp_code)
        
        if df_cap.empty:
            logging.warning(f"No market cap data found for {corp_code} from {start_date} to {end_date}.")
            return
        
        df_cap = df_cap.reset_index()
        df_cap.columns = ['trade_date', 'market_cap', 'outstanding_shares', 'foreign_ownership_rate', 'volume', 'trading_value']
        df_cap['corp_code'] = corp_code
        df_cap['bsns_year'] = bsns_year
        df_cap['reprt_code'] = reprt_code
        df_cap['trade_date'] = df_cap['trade_date'].dt.strftime('%Y%m%d')

        # Select relevant columns for storage
        df_to_store = df_cap[['corp_code', 'bsns_year', 'reprt_code', 'trade_date', 'outstanding_shares']]

        with _get_db_connection(db_path) as conn:
            df_to_store.to_sql('outstanding_shares_data', conn, if_exists='append', index=False)
        logging.info(f"Successfully stored outstanding shares for {corp_code}.")
    except Exception as e:
        logging.error(f"Error fetching/storing outstanding shares for {corp_code}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Fetch KRX stock data and store in DB.')
    parser.add_argument('--corp_code', type=str, required=True, help='Corporate code')
    parser.add_argument('--stock_code', type=str, required=True, help='Stock code')
    parser.add_argument('--bsns_year', type=int, required=True, help='Business year')
    parser.add_argument('--reprt_code', type=str, required=True, help='Report code')
    parser.add_argument('--start_date', type=str, required=True, help='Start date for data fetch (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, required=True, help='End date for data fetch (YYYYMMDD)')
    parser.add_argument('--db_path', type=str, required=True, help='Path to the SQLite database')

    args = parser.parse_args()

    fetch_and_store_stock_prices(args.db_path, args.stock_code, args.start_date, args.end_date)
    fetch_and_store_outstanding_shares(args.db_path, args.corp_code, args.bsns_year, args.reprt_code, args.start_date, args.end_date)

if __name__ == '__main__':
    main()
