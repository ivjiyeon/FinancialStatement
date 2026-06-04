import argparse
import sqlite3
import pandas as pd
from pykrx import stock
from datetime import datetime
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _get_db_connection(db_path: Path):
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(str(db_path))

def fetch_and_store_last_day_ohlcv_for_stock_prices_data(db_path: Path, stock_code: str, start_date: str, end_date: str):
    logging.info(f"Attempting to fetch OHLCV data for stock {stock_code} from {start_date} to {end_date}...")
    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, stock_code)
        logging.info(f"Successfully retrieved OHLCV data for {stock_code} ({len(df)} records).")

        if df.empty:
            logging.warning(f"No OHLCV data found for {stock_code} from {start_date} to {end_date}. Skipping storage in stock_prices_data.")
            return

        # Rename columns to English for consistency with database schema
        df = df.rename(columns={
            '시가': 'open_price',
            '고가': 'high_price',
            '저가': 'low_price',
            '종가': 'close_price',
            '거래량': 'volume'
        })

        # Get the last row (most recent trading day)
        last_row = df.iloc[-1]
        
        trade_date = df.index[-1].strftime('%Y%m%d') # Date from the index
        open_price = last_row['open_price']
        high_price = last_row['high_price']
        low_price = last_row['low_price']
        close_price = last_row['close_price']
        volume = last_row['volume']

        with _get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            # Use UPSERT to update if (stock_code, trade_date) exists, insert otherwise
            cursor.execute('''
                INSERT INTO stock_prices_data (stock_code, trade_date, open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stock_code, trade_date) DO UPDATE SET
                    open_price = excluded.open_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    close_price = excluded.close_price,
                    volume = excluded.volume
            ''', (stock_code, trade_date, open_price, high_price, low_price, close_price, volume))
            conn.commit()
        logging.info(f"Successfully stored OHLCV data for {stock_code} (close_price: {close_price}) on {trade_date}.")
    except Exception as e:
        logging.error(f"Failed to fetch or store OHLCV data for {stock_code} from {start_date} to {end_date}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Fetch KRX stock data and store in DB.')
    parser.add_argument('--corp_code', type=str, required=True, help='Corporate code')
    parser.add_argument('--stock_code', type=str, required=True, help='Stock code')
    # Removed bsns_year and reprt_code as they are no longer used by this worker script for outstanding shares
    parser.add_argument('--start_date', type=str, required=True, help='Start date for data fetch (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, required=True, help='End date for data fetch (YYYYMMDD)')
    parser.add_argument('--db_path', type=str, required=True, help='Path to the SQLite database')

    args = parser.parse_args()

    db_path = Path(args.db_path)

    # Call the existing function for OHLCV data
    fetch_and_store_last_day_ohlcv_for_stock_prices_data(db_path, args.stock_code, args.start_date, args.end_date)

if __name__ == '__main__':
    main()
