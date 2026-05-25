
import pandas as pd
import sqlite3
import os

def clean_amount(df, column_name):
    df[column_name] = df[column_name].astype(str).str.replace(',', '', regex=False)
    # Convert empty strings or '-' to 0 before converting to numeric
    df[column_name] = df[column_name].replace({'': '0', '-': '0'})
    df[column_name] = pd.to_numeric(df[column_name], errors='coerce').fillna(0).astype(int)
    return df

def process_and_store_data(file_path, table_name, conn):
    print(f"Processing {file_path}...")
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return

    # Select relevant columns
    # Adjusting for potential BOM in the first column name
    if '﻿rcept_no' in df.columns:
        df = df.rename(columns={'﻿rcept_no': 'rcept_no'})

    selected_columns = [
        'bsns_year',
        'account_id',
        'account_nm',
        'thstrm_amount',
        'frmtrm_amount',
        'bfefrmtrm_amount'
    ]

    # Filter columns that actually exist in the DataFrame
    df_filtered = df[[col for col in selected_columns if col in df.columns]].copy()

    # Clean and convert amount columns
    for col in ['thstrm_amount', 'frmtrm_amount', 'bfefrmtrm_amount']:
        if col in df_filtered.columns:
            df_filtered = clean_amount(df_filtered, col)
        else:
            print(f"Warning: Column '{col}' not found in {file_path}. Skipping cleaning.")

    # Store in SQLite
    df_filtered.to_sql(table_name, conn, if_exists='replace', index=False)
    print(f"Data from {file_path} stored successfully in {table_name}.")

def main():
    db_name = "financial_data.db"
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Define table schemas (basic for now, pandas to_sql will create them)
    # This part is more for conceptual clarity, pandas handles actual DDL
    # We will let pandas create the tables, but we know the structure will be based on the DataFrame.

    csv_files = {
        "bs.csv": "balance_sheet",
        "is.csv": "income_statement",
        "cf.csv": "cash_flow"
    }

    for csv_file, table_name in csv_files.items():
        process_and_store_data(csv_file, table_name, conn)

    # Verify data insertion
    print("\nVerifying data insertion from 'balance_sheet' table:")
    try:
        verification_query = "SELECT bsns_year, account_nm, thstrm_amount FROM balance_sheet LIMIT 5;"
        cursor.execute(verification_query)
        results = cursor.fetchall()
        for row in results:
            print(row)
    except sqlite3.Error as e:
        print(f"Error during verification: {e}")

    conn.close()
    print(f"Database '{db_name}' created and populated successfully.")

if __name__ == "__main__":
    main()
