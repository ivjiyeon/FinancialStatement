
import FinanceDataReader as fdr
import pandas as pd

try:
    # Try to get KRX listing information, which might contain sector data
    df_krx = fdr.StockListing('KRX')
    print(df_krx.head())

    # Check for sector-related columns
    if 'Sector' in df_krx.columns:
        print("\n'Sector' column found in KRX listing data:")
        print(df_krx[['Symbol', 'Name', 'Sector']].head())
    else:
        print("\n'Sector' column not found directly in KRX listing data.")
        print("Available columns:", df_krx.columns.tolist())

except Exception as e:
    print(f"An error occurred: {e}")

