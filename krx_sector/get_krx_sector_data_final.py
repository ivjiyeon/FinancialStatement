#!/usr/bin/env projects/financial_statement/venv/bin/python3.11
import pandas as pd
from pykrx import stock
from pykrx.website.krx.market import wrap as stock_wrap
from datetime import datetime

def get_krx_sector_data_pykrx():
    try:
        today = datetime.now().strftime('%Y%m%d')
        
        # Get all stock tickers for the given date (KOSPI and KOSDAQ)
        df_kospi = stock_wrap.get_market_sector_classifications(today, market="KOSPI")
        df_kosdaq = stock_wrap.get_market_sector_classifications(today, market="KOSDAQ")
        
        df = pd.concat([df_kospi, df_kosdaq])
        df = df.reset_index()

        if df.empty:
            print("No data received from pykrx. DataFrame is empty.")
            return pd.DataFrame()

        df = df[['종목코드', '종목명', '업종명']]
        df.columns = ['Stock Code', 'Stock Name', 'Sector Classification']

        df.to_csv("/home/ivjiyeonb/projects/financial_statement/data/krx_sector_data.csv", index=False, encoding='utf-8-sig')
        return df

    except Exception as e:
        print(f"An error occurred with pykrx: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("Attempting to acquire KRX sector data using pykrx...")
    df_sectors = get_krx_sector_data_pykrx()
    
    if not df_sectors.empty:
        print("\n--- Successfully acquired KRX sector data ---")
        print(df_sectors.head())
        print("\nTotal rows:", len(df_sectors))
        print("Columns:", df_sectors.columns.tolist())
    else:
        print("Failed to acquire KRX sector data using pykrx. DataFrame is empty.")