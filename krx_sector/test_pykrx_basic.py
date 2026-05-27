import os
import sys
import pandas as pd
import logging
from datetime import datetime
from dotenv import load_dotenv
from pykrx.stock import get_market_ohlcv_by_ticker, get_market_fundamental_by_ticker

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_fetch_data(stock_code, trade_date_str):
    logging.info(f"Testing pykrx for {stock_code} on {trade_date_str}")
    
    try:
        # Test OHLCV
        df_ohlcv = get_market_ohlcv_by_ticker(trade_date_str, stock_code)
        if not df_ohlcv.empty:
            logging.info(f"OHLCV data for {stock_code} on {trade_date_str}:\n{df_ohlcv.to_string()}")
        else:
            logging.warning(f"No OHLCV data found for {stock_code} on {trade_date_str}.")

        # Test Fundamental
        df_fundamental = get_market_fundamental_by_ticker(trade_date_str, stock_code)
        if not df_fundamental.empty:
            logging.info(f"Fundamental data for {stock_code} on {trade_date_str}:\n{df_fundamental.to_string()}")
        else:
            logging.warning(f"No fundamental data found for {stock_code} on {trade_date_str}.")

    except Exception as e:
        logging.error(f"Error during pykrx test for {stock_code} on {trade_date_str}: {e}")

if __name__ == "__main__":
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../.env'))
    
    # Test with Samsung Electronics on a known past date
    test_fetch_data("005930", "20240524")
    logging.info("Pykrx basic test finished.")
