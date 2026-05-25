import requests
import pandas as pd
import io
from datetime import datetime

def get_krx_sector_data():
    try:
        # URL for direct CSV download of stock listings
        # This endpoint is known to provide a general listing that *might* include sector data.
        download_url = 'http://data.krx.co.kr/comm/bldAttendant/getBldAttendantWithArgs.cmd'

        today_str = datetime.now().strftime('%Y%m%d')

        # Parameters for the general stock listing, requesting CSV directly.
        # bld MDCSTAT01901 is for general stock listings.
        download_params = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',
            'mktId': 'ALL',  # All markets
            'trdDd': today_str, # A recent date, format YYYYMMDD
            'share': '1',
            'money': '1',
            'csvxls_isNo': 'false', # Requesting direct CSV download
            'name': 'fileDown',
            'filetype': 'csv'
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "http://data.krx.co.kr/"
        }

        print("Attempting direct CSV download of general stock listing...")
        response = requests.post(download_url, data=download_params, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors

        # Read the CSV content into a pandas DataFrame
        df = pd.read_csv(io.StringIO(response.text))
        print("Successfully downloaded and parsed CSV data.")
        return df

    except requests.exceptions.RequestException as req_e:
        print(f"A request error occurred: {req_e}")
        if req_e.response is not None:
            print(f"Response content (if available): {req_e.response.text[:500]}...")
        return pd.DataFrame()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("Attempting to acquire KRX sector data via direct listing download...")
    df_sectors = get_krx_sector_data()
    
    if not df_sectors.empty:
        print("\n--- Raw Data Head ---")
        print(df_sectors.head())
        print("\n--- Raw Data Columns ---")
        print(df_sectors.columns.tolist())

        # Now, check for columns that might contain sector information.
        # Common column names for sector/industry are '업종명', '산업', '섹터', etc.
        # In English, these might appear as 'Sector', 'Industry'.
        
        # Let's prioritize '업종명' (Industry Name).
        # If '업종명' is not present, we will report that sector data is missing.

        required_cols = ['종목코드', '종목명', '업종명']
        present_cols = [col for col in required_cols if col in df_sectors.columns]

        if len(present_cols) == 3:
            result_df = df_sectors[present_cols].copy()
            result_df.columns = ['Stock Code', 'Stock Name', 'Sector Classification']
            print("\n--- Final Processed DataFrame Head ---")
            print(result_df.head())
            print("\n--- Final Processed DataFrame Columns ---")
            print(result_df.columns.tolist())
        else:
            print("\nWarning: Not all required columns ('종목코드', '종목명', '업종명') were found.")
            print("Available columns:", df_sectors.columns.tolist())
            print("Sector classification data could not be fully extracted from the general listing.")
    else:
        print("Failed to acquire KRX sector data. DataFrame is empty.")
