import os
import logging
from pykrx import stock
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Hardcode KRX credentials for this test (normally from .env)
    # These will be overridden by environment variables if set by the caller.
    # For testing the worker directly, we might need to set them here,
    # or ensure the parent process sets them.

def run_test():
    test_stock_code = "005930"  # Samsung Electronics
    test_corp_code = "00126380" # Corp code for Samsung
    test_end_date_obj = datetime(2023, 1, 31)
    test_start_date_obj = datetime(2023, 1, 1)
    test_end_date = test_end_date_obj.strftime("%Y%m%d")
    test_start_date = test_start_date_obj.strftime("%Y%m%d")

    logging.info(f"--- Running pykrx test for {test_stock_code} ({test_corp_code}) ---")
    logging.info(f"Date Range: {test_start_date} to {test_end_date}")

    # Test stock prices
    try:
        logging.info("Fetching stock prices (OHLCV)...")
        df_ohlcv = stock.get_market_ohlcv_by_date(test_start_date, test_end_date, test_stock_code)
        if not df_ohlcv.empty:
            logging.info(f"Successfully fetched {len(df_ohlcv)} stock price records.")
            logging.info(f"Sample OHLCV:\n{df_ohlcv.head()}")
        else:
            logging.warning("No OHLCV data returned.")
    except Exception as e:
        logging.error(f"Error fetching OHLCV: {e}")

    # Test market cap (outstanding shares)
    try:
        logging.info("Fetching market cap data (outstanding shares)...")
        df_cap = stock.get_market_cap_by_date(test_start_date, test_end_date, test_corp_code)
        if not df_cap.empty:
            logging.info(f"Successfully fetched {len(df_cap)} market cap records.")
            logging.info(f"Sample Market Cap:\n{df_cap.head()}")
        else:
            logging.warning("No market cap data returned.")
    except Exception as e:
        logging.error(f"Error fetching market cap: {e}")

    logging.info("--- pykrx test completed ---")

if __name__ == "__main__":
    # Ensure KRX credentials are in the environment for this direct run
    # For a direct test, I'll print a reminder if they're not set.
    if 'KRX_ID' not in os.environ or 'KRX_PW' not in os.environ:
        logging.warning("KRX_ID or KRX_PW not set in environment. pykrx may fail.")
        logging.warning("Please set KRX_ID and KRX_PW environment variables.")

    run_test()
