import sys
import os
import sqlite3
import pandas as pd
import logging
from datetime import datetime

# Dynamically add the project root to sys.path
# This assumes the script is in a subdirectory like 'scripts/'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from dart.util import _get_reporting_period_end_date

class FinancialAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            logging.error(f"Database not found at {self.db_path}")
            raise FileNotFoundError(f"Database not found at {self.db_path}")

    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def load_company_info(self):
        logging.info("Loading company information...")
        with self._get_db_connection() as conn:
            company_info_df = pd.read_sql_query("SELECT corp_code, stock_code, corp_name, corp_eng_name FROM company_info", conn, dtype={
                'corp_code': str,
                'stock_code': str,
                'corp_name': str,
                'corp_eng_name': str
            })
        logging.info(f"Loaded {len(company_info_df)} company records.")
        return company_info_df

    def load_financial_statements(self, bsns_year, reprt_code):
        logging.info(f"Loading financial statements for year {bsns_year}, report {reprt_code}...")
        with self._get_db_connection() as conn:
            query = f"""
                SELECT
                    fsi.corp_code,
                    fsi.bsns_year,
                    fsi.reprt_code,
                    fsi.sj_div,
                    sm.fs_div,
                    fsi.account_nm,
                    fsi.account_id,
                    fsi.thstrm_amount
                FROM financial_statement_items AS fsi
                JOIN statement_metadata AS sm
                ON fsi.corp_code = sm.corp_code
                AND fsi.bsns_year = sm.bsns_year
                AND fsi.reprt_code = sm.reprt_code
                AND fsi.sj_div = sm.sj_div
                WHERE fsi.bsns_year = {bsns_year} AND fsi.reprt_code = '{reprt_code}'
            """
            financial_df = pd.read_sql_query(query, conn, dtype={
                'corp_code': str,
                'bsns_year': 'int16',
                'reprt_code': str,
                'sj_div': 'category',
                'fs_div': 'category',
                'account_nm': str,
                'thstrm_amount': 'float32'
            })
        logging.info(f"Loaded {len(financial_df)} financial statement records.")
        return financial_df

    def load_outstanding_shares(self, bsns_year, reprt_code):
        logging.info(f"Loading outstanding shares for year {bsns_year}, report {reprt_code}...")
        with self._get_db_connection() as conn:
            query = f"""
                SELECT
                    corp_code,
                    bsns_year,
                    reprt_code,
                    outstanding_shares
                FROM outstanding_shares
                WHERE bsns_year = {bsns_year} AND reprt_code = '{reprt_code}'
            """
            shares_df = pd.read_sql_query(query, conn, dtype={
                'corp_code': str,
                'bsns_year': 'int16',
                'reprt_code': str,
                'outstanding_shares': 'int64'
            })
        logging.info(f"Loaded {len(shares_df)} outstanding shares records.")
        return shares_df

    def load_stock_prices(self, trade_date_str):
        logging.info(f"Loading stock prices for date {trade_date_str}...")
        with self._get_db_connection() as conn:
            query = f"""
                SELECT
                    stock_code,
                    trade_date,
                    close_price
                FROM stock_prices
                WHERE trade_date = '{trade_date_str}'
            """
            prices_df = pd.read_sql_query(query, conn, dtype={
                'stock_code': str,
                'trade_date': str,
                'close_price': 'int64'
            })
        logging.info(f"Loaded {len(prices_df)} stock price records.")
        return prices_df

    def calculate_financial_ratios(self, financial_df, company_info_df):
        logging.info("Calculating financial ratios...")
        if financial_df.empty:
            logging.warning("Financial DataFrame is empty, cannot calculate ratios.")
            return pd.DataFrame()

        logging.debug(f"financial_df columns: {financial_df.columns.tolist()}")
        if 'account_id' not in financial_df.columns:
            logging.error("Critical Error: 'account_id' column missing in financial_df.")
            return pd.DataFrame()
        logging.debug(f"Unique account_id values (sample): {financial_df['account_id'].unique()[:5].tolist()}...")
        if financial_df['account_id'].isnull().any():
            logging.warning("financial_df contains NaN values in 'account_id' column.")

        # Extract and pivot Balance Sheet (BS) data
        bs_df = financial_df[financial_df['sj_div'] == 'BS'].pivot_table(
            index=['corp_code', 'bsns_year', 'reprt_code'],
            columns='account_id', values='thstrm_amount', aggfunc='first'
        ).reset_index()
        bs_df.columns.name = None
        bs_df = bs_df.rename(columns={col: f'BS_{col}' for col in bs_df.columns if col not in ['corp_code', 'bsns_year', 'reprt_code']})

        # Extract and pivot Income Statement (IS) data
        is_df = financial_df[financial_df['sj_div'] == 'IS'].pivot_table(
            index=['corp_code', 'bsns_year', 'reprt_code'],
            columns='account_id', values='thstrm_amount', aggfunc='first'
        ).reset_index()
        is_df.columns.name = None
        is_df = is_df.rename(columns={col: f'IS_{col}' for col in is_df.columns if col not in ['corp_code', 'bsns_year', 'reprt_code']})

        # Extract and pivot Cash Flow Statement (CF) data
        cfs_df = financial_df[financial_df['sj_div'] == 'CF'].pivot_table(
            index=['corp_code', 'bsns_year', 'reprt_code'],
            columns='account_id', values='thstrm_amount', aggfunc='first'
        ).reset_index()
        cfs_df.columns.name = None
        cfs_df = cfs_df.rename(columns={col: f'CF_{col}' for col in cfs_df.columns if col not in ['corp_code', 'bsns_year', 'reprt_code']})

        # Merge all financial statements and company info
        merged_df = pd.merge(bs_df, is_df, on=['corp_code', 'bsns_year', 'reprt_code'], how='outer', suffixes=('_bs', '_is'))
        merged_df = pd.merge(merged_df, cfs_df, on=['corp_code', 'bsns_year', 'reprt_code'], how='outer', suffixes=('', '_cfs'))

        company_info_df_processed = company_info_df[['corp_code', 'stock_code', 'corp_name']].drop_duplicates(subset=['corp_code'])
        merged_df = pd.merge(merged_df, company_info_df_processed, on='corp_code', how='left')

        # Load outstanding shares and merge
        shares_df = self.load_outstanding_shares(merged_df['bsns_year'].iloc[0], merged_df['reprt_code'].iloc[0])
        merged_df = pd.merge(merged_df, shares_df, on=['corp_code', 'bsns_year', 'reprt_code'], how='left')
        merged_df['outstanding_shares'] = merged_df['outstanding_shares'].fillna(pd.NA) # Fill NaN with pd.NA

        # Load stock prices and merge, using the same reporting period end date for consistency
        target_stock_price_date = _get_reporting_period_end_date(merged_df['bsns_year'].iloc[0], merged_df['reprt_code'].iloc[0])
        prices_df = self.load_stock_prices(target_stock_price_date)
        merged_df = pd.merge(merged_df, prices_df[['stock_code', 'close_price']], on='stock_code', how='left')
        merged_df['close_price'] = merged_df['close_price'].fillna(pd.NA) # Fill NaN with pd.NA

        # Initialize ratio columns with 0.0 or None
        ratio_cols = ['Total_Assets', 'Total_Equity', 'Total_Liabilities', 'Current_Assets', 'Current_Liabilities', 
                      'Net_Income', 'Operating_Cash_Flow', 'D_E_Ratio', 'Current_Ratio', 'ROE', 'ROA',
                      'EPS', 'BPS', 'PER', 'PBR']
        for col in ratio_cols:
            if col not in merged_df.columns:
                merged_df[col] = pd.NA # Initialize with pd.NA instead of 0.0

        # --- Ratio Calculations ---
        # Balance Sheet Items
        merged_df['Total_Assets'] = merged_df.get('BS_ifrs-full_Assets', pd.Series([0.0] * len(merged_df))).fillna(0.0)
        merged_df['Total_Equity'] = merged_df.get('BS_ifrs-full_Equity', pd.Series([0.0] * len(merged_df))).fillna(0.0)
        merged_df['Total_Liabilities'] = merged_df.get('BS_ifrs-full_Liabilities', pd.Series([0.0] * len(merged_df))).fillna(0.0)
        merged_df['Current_Assets'] = merged_df.get('BS_ifrs-full_CurrentAssets', pd.Series([0.0] * len(merged_df))).fillna(0.0)
        merged_df['Current_Liabilities'] = merged_df.get('BS_ifrs-full_CurrentLiabilities', pd.Series([0.0] * len(merged_df))).fillna(0.0)

        # Income Statement Items
        merged_df['Net_Income'] = merged_df.get('IS_ifrs-full_ProfitLoss', pd.Series([0.0] * len(merged_df))).fillna(0.0)

        # Cash Flow Statement Items
        merged_df['Operating_Cash_Flow'] = merged_df.get('CF_ifrs-full_CashFlowsFromUsedInOperatingActivities', pd.Series([0.0] * len(merged_df))).fillna(0.0)

        # Debt-to-Equity Ratio
        merged_df['D_E_Ratio'] = merged_df['Total_Liabilities'] / merged_df['Total_Equity']
        merged_df['D_E_Ratio'] = merged_df['D_E_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA) # Handle division by zero or NaN

        # Current Ratio
        merged_df['Current_Ratio'] = merged_df['Current_Assets'] / merged_df['Current_Liabilities']
        merged_df['Current_Ratio'] = merged_df['Current_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA) # Handle division by zero or NaN

        # ROE (Return on Equity)
        merged_df['ROE'] = merged_df['Net_Income'] / merged_df['Total_Equity']
        merged_df['ROE'] = merged_df['ROE'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA) # Handle division by zero or NaN

        # ROA (Return on Assets)
        merged_df['ROA'] = merged_df['Net_Income'] / merged_df['Total_Assets']
        merged_df['ROA'] = merged_df['ROA'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA) # Handle division by zero or NaN

        # EPS (Earnings Per Share)
        merged_df['EPS'] = merged_df['Net_Income'] / merged_df['outstanding_shares']
        merged_df['EPS'] = merged_df['EPS'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # BPS (Book Value Per Share)
        merged_df['BPS'] = merged_df['Total_Equity'] / merged_df['outstanding_shares']
        merged_df['BPS'] = merged_df['BPS'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # PER (Price-to-Earnings Ratio)
        merged_df['PER'] = merged_df['close_price'] / merged_df['EPS']
        merged_df['PER'] = merged_df['PER'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # PBR (Price-to-Book Ratio)
        merged_df['PBR'] = merged_df['close_price'] / merged_df['BPS']
        merged_df['PBR'] = merged_df['PBR'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        logging.info("Financial ratios calculated.")
        return merged_df

    def identify_undervalued_companies(self, analysis_df):
        logging.info("Identifying undervalued companies with updated criteria...")
        if analysis_df.empty:
            logging.warning("Analysis DataFrame is empty, cannot identify undervalued companies.")
            return pd.DataFrame(), [], [], [] # Return empty list for corp_codes

        # Drop rows where essential ratios cannot be calculated (e.g., due to missing base values)
        # For now, let's focus on D_E_Ratio, Current_Ratio, ROE, Operating_Cash_Flow
        initial_companies = analysis_df.dropna(subset=['D_E_Ratio', 'Current_Ratio', 'ROE', 'Operating_Cash_Flow'])
        logging.info(f"Initial candidates after dropping NA for key ratios: {len(initial_companies)} companies.")
        
        if initial_companies.empty:
            logging.info("No companies remain after dropping NA for essential ratios.")
            return pd.DataFrame(), [], [], []

        # --- Stage 1: Financial Health Check ---
        logging.info("Applying Stage 1: Financial Health Check (Debt-to-Equity <= 100%, Current Ratio >= 150%)...")
        stage1_filtered_companies = initial_companies[
            (initial_companies['D_E_Ratio'] <= 1.0) &  # 부채비율 100% 이하
            (initial_companies['Current_Ratio'] >= 1.5) # 유동비율 150% 이상
        ].copy()
        stage1_passed_corp_codes = stage1_filtered_companies['corp_code'].tolist()
        logging.info(f"Stage 1 passed: {len(stage1_passed_corp_codes)} companies.")

        if stage1_filtered_companies.empty:
            logging.info("No companies passed Stage 1 financial health check.")
            return pd.DataFrame(), [], [], []

        # --- Stage 2: Profitability and Asset Value Verification ---
        logging.info("Applying Stage 2: Profitability and Asset Value Verification (ROE >= 10%, Operating Cash Flow > 0)...")
        # Note on "꾸준히 상승/증가": This currently only checks the latest period. For multi-period check, historical data is needed.
        stage2_filtered_companies = stage1_filtered_companies[
            (stage1_filtered_companies['ROE'] >= 0.10) & # ROE 10% 이상
            (stage1_filtered_companies['Operating_Cash_Flow'] > 0) # 영업활동 현금흐름 양수
        ].copy()
        stage2_passed_corp_codes = stage2_filtered_companies['corp_code'].tolist()
        logging.info(f"Stage 2 passed: {len(stage2_passed_corp_codes)} companies.")

        self.save_filtered_companies(stage2_passed_corp_codes, analysis_df['bsns_year'].iloc[0], analysis_df['reprt_code'].iloc[0])

        if stage2_filtered_companies.empty:
            logging.info("No companies passed Stage 2 profitability and asset value verification.")
            return pd.DataFrame(), stage1_passed_corp_codes, [], []

        # --- Stage 3: Valuation Metrics (PER, PBR) ---
        logging.info("Applying Stage 3: Valuation Metrics (PER > 0, PBR > 0)...")
        stage3_filtered_companies = stage2_filtered_companies[
            (stage2_filtered_companies['PER'] > 0) & # PER 0 초과
            (stage2_filtered_companies['PBR'] > 0) # PBR 0 초과
        ].copy()
        stage3_passed_corp_codes = stage3_filtered_companies['corp_code'].tolist()
        logging.info(f"Stage 3 passed: {len(stage3_passed_corp_codes)} companies.")
        
        if stage3_filtered_companies.empty:
            logging.info("No companies remain after Stage 3.")
            return pd.DataFrame(), stage1_passed_corp_codes, stage2_passed_corp_codes, []

        logging.info(f"Identified {len(stage3_filtered_companies)} potentially undervalued companies based on systematic criteria.")
        return stage3_filtered_companies, stage1_passed_corp_codes, stage2_passed_corp_codes, stage3_passed_corp_codes

    def save_filtered_companies(self, corp_codes, bsns_year, reprt_code):
        logging.info(f"Saving {len(corp_codes)} filtered companies to database for {bsns_year}-{reprt_code}...")
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS filtered_companies;") # Correct position
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS filtered_companies (
                    corp_code TEXT NOT NULL,
                    bsns_year INTEGER NOT NULL,
                    reprt_code TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    PRIMARY KEY (corp_code, bsns_year, reprt_code)
                )
            """)
            conn.commit()

            insert_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"DEBUG: Type of bsns_year before insert: {type(bsns_year)}")
            logging.info(f"DEBUG: Value of bsns_year before insert: {bsns_year}")
            for corp_code in corp_codes:
                cursor.execute("""
                    INSERT OR REPLACE INTO filtered_companies (corp_code, bsns_year, reprt_code, analysis_date)
                    VALUES (?, ?, ?, ?)
                """, (corp_code, int(bsns_year), reprt_code, insert_date)) # CAST TO INT HERE
            conn.commit()
        logging.info("Filtered companies saved successfully.")

def main():
    PROJECT_ROOT = '/home/ivjiyeonb/projects/financial_statement/'
    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'financial_data.db')
    
    # --- Configuration for data fetching ---
    # This part should ideally be dynamic or passed as arguments for different quarters
    # For initial testing, let's use 2024 Q3 (11013) as we successfully fetched it.
    TARGET_BSNS_YEAR = 2025
    TARGET_REPRT_CODE = '11011' # 11013 for Q3, 11012 for Q2, 11011 for Q4 (Annual), 11014 for Q1

    try:
        analyzer = FinancialAnalyzer(DB_PATH)
        
        company_info_df = analyzer.load_company_info()
        financial_df = analyzer.load_financial_statements(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)
        
        # Check if financial_df has 'thstrm_amount' before calculating ratios
        if 'thstrm_amount' not in financial_df.columns:
            logging.error("'thstrm_amount' column not found in financial statements, cannot proceed with ratio calculation.")
            return

        analysis_df = analyzer.calculate_financial_ratios(financial_df, company_info_df)
        undervalued_companies_df, stage1_codes, stage2_codes, stage3_codes = analyzer.identify_undervalued_companies(analysis_df)
        
        if not undervalued_companies_df.empty:
            logging.info("--- Undervalued Companies Identified (Final List) ---")
            print(undervalued_companies_df[['corp_name', 'stock_code', 'ROE', 'ROA', 'D_E_Ratio', 'Current_Ratio', 'Operating_Cash_Flow']].to_string())
            logging.info(f"\nStage 1 (Financial Health) Passed Companies ({len(stage1_codes)}): {stage1_codes}")
            logging.info(f"Stage 2 (Profitability/Asset Value) Passed Companies ({len(stage2_codes)}): {stage2_codes}")
            logging.info(f"Stage 3 (Valuation Metrics) Passed Companies ({len(stage3_codes)}): {stage3_codes}")
        else:
            logging.info("No undervalued companies found based on current criteria.")
            logging.info(f"\nStage 1 (Financial Health) Passed Companies ({len(stage1_codes)}): {stage1_codes}")
            logging.info(f"Stage 2 (Profitability/Asset Value) Passed Companies ({len(stage2_codes)}): {stage2_codes}")
            
    except FileNotFoundError as e:
        logging.error(e)
    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}")

if __name__ == "__main__":
    main()
