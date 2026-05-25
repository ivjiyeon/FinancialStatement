
import OpenDartReader
import FinanceDataReader as fdr
import pandas as pd
import sqlite3
import os
from dotenv import load_dotenv # Added

# Load environment variables from .env file
# Assuming .env is in the parent directory relative to the script
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')) # Added

# FSS DART API Key
DART_API_KEY = os.getenv("DART_API_KEY") # Modified
if not DART_API_KEY:
    raise ValueError("DART_API_KEY not found in environment variables or .env file.")

DB_PATH = "/home/ivjiyeonb/projects/financial_statement/data/financial_data.db" # Modified path to data folder

def populate_company_info():
    # 1. Use OpenDartReader to get the list of all companies
    print("Fetching company codes from DART...")
    dart = OpenDartReader(DART_API_KEY)
    dart_companies = dart.corp_codes
    # Ensure stock_code is a string for merging
    dart_companies['stock_code'] = dart_companies['stock_code'].astype(str)
    print(f"Fetched {len(dart_companies)} companies from DART.")

    # 2. Use finance-datareader to get stock listing for KRX
    print("Fetching stock listings from FinanceDataReader...")
    fdr_krx = fdr.StockListing('KRX')
    # Ensure 'Symbol' is a string for merging and remove '.KS' or '.KQ' suffix
    fdr_krx['Code'] = fdr_krx['Code'].astype(str).str.replace(r'\\.K[S|Q]', '', regex=True)
    print(f"Fetched {len(fdr_krx)} stock listings from FinanceDataReader.")

    # 3. Merge these two dataframes
    print("Merging dataframes...")
    # Rename columns for clarity before merging
    fdr_krx_renamed = fdr_krx.rename(columns={'Code': 'stock_code', 'Name': 'company_name'})
    
    # Perform a left merge to keep all DART companies and add FDR info
    company_info = pd.merge(dart_companies, fdr_krx_renamed[['stock_code', 'company_name', 'Market']], 
                            on='stock_code', 
                            how='left')
    
    # Filter out companies without a stock_code (meaning no match in FDR data or no stock_code from DART)
    company_info = company_info[company_info['stock_code'].notna() & (company_info['stock_code'] != '')]
    
    # Select and reorder columns to match the requirement
    company_info = company_info[['corp_code', 'stock_code', 'company_name', 'Market']]
    
    # Handle potential duplicates if any (e.g., if a stock code appears multiple times in DART with different corp_codes, though less likely)
    company_info.drop_duplicates(subset=['corp_code', 'stock_code'], inplace=True)

    print("Merged company_info DataFrame created.")
    
    # 5. Print the head of the created company_info DataFrame
    print("\nHead of company_info DataFrame:")
    print(company_info.head())

    # 4. Stores this company_info DataFrame into a new table named company_info within financial_data.db
    print(f"Saving company_info to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    try:
        company_info.to_sql('company_info', conn, if_exists='replace', index=False)
        print("company_info table created/updated successfully in the database.")
    except Exception as e:
        print(f"Error saving to database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    populate_company_info()
