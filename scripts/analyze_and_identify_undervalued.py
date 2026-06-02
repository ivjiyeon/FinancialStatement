import sys
import os
import sqlite3
import pandas as pd
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Dynamically add the project root to sys.path
# This assumes the script is in a subdirectory like 'scripts/'
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = os.path.join(PROJECT_ROOT, 'scripts/analyze_and_identify_undervalued.log')
sys.path.append(str(PROJECT_ROOT))

from dart.util import _get_reporting_period_end_date, determine_recent_report_code_and_year
from scripts.financial_metrics import calculate_per_pbr

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
            query = """
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
                WHERE fsi.bsns_year = ? AND fsi.reprt_code = ?
            """
            financial_df = pd.read_sql_query(query, conn, params=(bsns_year, reprt_code), dtype={
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
        target_trade_date = _get_reporting_period_end_date(bsns_year, reprt_code)
        with self._get_db_connection() as conn:
            query = """
                SELECT
                    corp_code,
                    trade_date,
                    outstanding_shares
                FROM outstanding_shares_data
                WHERE trade_date = ?
            """
            shares_df = pd.read_sql_query(query, conn, params=(target_trade_date,), dtype={
                'corp_code': str,
                'trade_date': str,
                'outstanding_shares': 'int64'
            })
        logging.info(f"Loaded {len(shares_df)} outstanding shares records.")
        return shares_df

    def load_stock_prices(self, trade_date_str):
        logging.info(f"Loading stock prices for date {trade_date_str}...")
        with self._get_db_connection() as conn:
            query = """
                SELECT
                    stock_code,
                    trade_date,
                    close_price
                FROM stock_prices_data
                WHERE trade_date = ?
            """
            prices_df = pd.read_sql_query(query, conn, params=(trade_date_str,), dtype={
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
        merged_df = pd.merge(merged_df, shares_df[['corp_code', 'outstanding_shares']], on='corp_code', how='left')
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

        # Calculate PER and PBR using the new module
        logging.info("Calculating PER and PBR using financial_metrics module...")
        per_list = []
        pbr_list = []
        for index, row in merged_df.iterrows():
            corp_code = row['corp_code']
            stock_code = row['stock_code']
            bsns_year = str(row['bsns_year']) # Ensure bsns_year is string
            
            per, pbr = calculate_per_pbr(corp_code, stock_code, bsns_year, self.db_path)
            per_list.append(per)
            pbr_list.append(pbr)
        
        merged_df['PER'] = pd.Series(per_list, dtype=float)
        merged_df['PBR'] = pd.Series(pbr_list, dtype=float)
        
        logging.info("Financial ratios calculated.")
        return merged_df





    def _apply_stage1_and_2_filters(self, analysis_df):
        logging.info("Applying Stage 1 & 2 filters...")
        if analysis_df.empty:
            logging.warning("Analysis DataFrame is empty, cannot apply Stage 1 & 2 filters.")
            return pd.DataFrame()

        # Drop rows where essential ratios cannot be calculated (e.g., due to missing base values)
        initial_companies = analysis_df.dropna(subset=['D_E_Ratio', 'Current_Ratio', 'ROE', 'Operating_Cash_Flow'])

        # Define filter constants
        DEBT_TO_EQUITY_RATIO_THRESHOLD = 1.0  # 100%
        CURRENT_RATIO_THRESHOLD = 1.5       # 150%
        ROE_THRESHOLD = 0.10                # 10%
        OPERATING_CASH_FLOW_THRESHOLD = 0   # > 0

        if initial_companies.empty:
            logging.info("No companies remain after dropping NA for essential ratios for Stage 1 & 2.")
            return pd.DataFrame()

        # --- Stage 1: Financial Health Check ---
        logging.info(f"Applying Stage 1: Financial Health Check (Debt-to-Equity <= {DEBT_TO_EQUITY_RATIO_THRESHOLD*100}%, Current Ratio >= {CURRENT_RATIO_THRESHOLD*100}%)...")
        stage1_filtered_companies = initial_companies[
            (initial_companies['D_E_Ratio'] <= DEBT_TO_EQUITY_RATIO_THRESHOLD) &  # 부채비율 100% 이하
            (initial_companies['Current_Ratio'] >= CURRENT_RATIO_THRESHOLD) # 유동비율 150% 이상
        ].copy()
        logging.info(f"Stage 1 passed: {len(stage1_filtered_companies)} companies.")

        if stage1_filtered_companies.empty:
            logging.info("No companies passed Stage 1 financial health check.")
            return pd.DataFrame()

        # --- Stage 2: Profitability and Asset Value Verification ---
        logging.info(f"Applying Stage 2: Profitability and Asset Value Verification (ROE >= {ROE_THRESHOLD*100}%, Operating Cash Flow > {OPERATING_CASH_FLOW_THRESHOLD})...")
        stage2_filtered_companies = stage1_filtered_companies[
            (stage1_filtered_companies['ROE'] >= ROE_THRESHOLD) & # ROE 10% 이상
            (stage1_filtered_companies['Operating_Cash_Flow'] > OPERATING_CASH_FLOW_THRESHOLD) # 영업활동 현금흐름 양수
        ].copy()
        logging.info(f"Stage 2 passed: {len(stage2_filtered_companies)} companies.")

        return stage2_filtered_companies

    def _load_filtered_companies_for_stage3(self, bsns_year, reprt_code):
        logging.info(f"Loading companies from filtered_companies table for {bsns_year}-{reprt_code}...")
        with self._get_db_connection() as conn:
            query = """
                SELECT
                    fc.corp_code,
                    ci.stock_code,
                    ci.corp_name,
                    fc.bsns_year,
                    fc.reprt_code
                FROM filtered_companies AS fc
                JOIN company_info AS ci ON fc.corp_code = ci.corp_code
                WHERE fc.bsns_year = ? AND fc.reprt_code = ?
            """
            filtered_companies_df = pd.read_sql_query(query, conn, params=(bsns_year, reprt_code), dtype={
                'corp_code': str,
                'stock_code': str,
                'corp_name': str,
                'bsns_year': 'int16',
                'reprt_code': str
            })
        logging.info(f"Loaded {len(filtered_companies_df)} companies for Stage 3 from filtered_companies table.")
        return filtered_companies_df

    def _apply_stage3_filters(self, analysis_df):
        logging.info("Applying Stage 3: Valuation Metrics (P/E > 0, P/E < 15.0, P/B > 0, P/B < 1.5)...")
        if analysis_df.empty:
            logging.warning("Analysis DataFrame is empty, cannot apply Stage 3 filters.")
            return pd.DataFrame()

        # Define filter constants for Stage 3
        PER_MAX = 15.0
        PBR_MAX = 1.5

        # Companies failing Stage 3 will be logged
        failed_stage3_per = analysis_df[
            ~((analysis_df['PER'].notna()) & (analysis_df['PER'] > 0) & (analysis_df['PER'] < PER_MAX))
        ]
        for idx, row in failed_stage3_per.iterrows():
            logging.info(f"Company {row['corp_name']} (PER={row.get('PER', 'N/A'):.2f}) failed Stage 3 (P/E not within 0-{PER_MAX} or N/A).")

        failed_stage3_pbr = analysis_df[
            ~((analysis_df['PBR'].notna()) & (analysis_df['PBR'] > 0) & (analysis_df['PBR'] < PBR_MAX))
        ]
        for idx, row in failed_stage3_pbr.iterrows():
            logging.info(f"Company {row['corp_name']} (PBR={row.get('PBR', 'N/A'):.2f}) failed Stage 3 (P/B not within 0-{PBR_MAX} or N/A).")

        stage3_filtered_companies = analysis_df[
            (analysis_df['PER'].notna()) & (analysis_df['PER'] > 0) & (analysis_df['PER'] < PER_MAX) &
            (analysis_df['PBR'].notna()) & (analysis_df['PBR'] > 0) & (analysis_df['PBR'] < PBR_MAX)
        ].copy()

        logging.info(f"Stage 3 passed: {len(stage3_filtered_companies)} companies.")
        return stage3_filtered_companies

    def save_filtered_companies(self, corp_codes, bsns_year, reprt_code, append=False):
        logging.info(f"Saving {len(corp_codes)} filtered companies to database for {bsns_year}-{reprt_code}...")
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            if not append: # If not appending, drop table to start fresh (for Stage 1&2 or full run)
                cursor.execute("DROP TABLE IF EXISTS filtered_companies;")
                logging.info("Dropped existing filtered_companies table.")

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
            data_to_insert = [(corp_code, int(bsns_year), reprt_code, insert_date) for corp_code in corp_codes]
            cursor.executemany("""
                INSERT OR REPLACE INTO filtered_companies (corp_code, bsns_year, reprt_code, analysis_date)
                VALUES (?, ?, ?, ?)
            """, data_to_insert)
            conn.commit()
        logging.info("Filtered companies saved successfully.")

def main():
    # Configure logging to go to the specified log file
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(description="Analyze financial statements to identify undervalued companies.")
    parser.add_argument('--stage', type=str, choices=['1_2', '3', 'all'], default='all',
                        help="Specify the analysis stage to run: '1_2' for initial filtering, '3' for valuation metrics, or 'all' for sequential execution.")
    args = parser.parse_args()

    PROJECT_ROOT_DIR = Path('/home/ivjiyeonb/projects/financial_statement/')
    DB_PATH = PROJECT_ROOT_DIR / 'data' / 'financial_data.db'

    # --- Configuration for data fetching ---
    current_date = datetime.now()
    TARGET_BSNS_YEAR, TARGET_REPRT_CODE, display_quarter = determine_recent_report_code_and_year(current_date)
    
    # Report codes constants (kept for context, but values determined dynamically)
    Q1_REPRT_CODE = '11014'
    Q2_REPRT_CODE = '11012'
    Q3_REPRT_CODE = '11013'
    ANNUAL_REPRT_CODE = '11011' # Q4 (Annual)

    report_output = [] # List to store report sections

    try:
        analyzer = FinancialAnalyzer(DB_PATH)

        if args.stage == '1_2' or args.stage == 'all':
            logging.info("--- Running Stage 1 & 2: Financial Health and Profitability Check ---")
            company_info_df = analyzer.load_company_info()
            financial_df = analyzer.load_financial_statements(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

            if 'thstrm_amount' not in financial_df.columns:
                logging.error("'thstrm_amount' column not found in financial statements, cannot proceed with ratio calculation.")
                return "" # Return empty string on error

            analysis_df_all_ratios = analyzer.calculate_financial_ratios(financial_df, company_info_df)

            stage2_filtered_companies = analyzer._apply_stage1_and_2_filters(analysis_df_all_ratios)

            if not stage2_filtered_companies.empty:
                analyzer.save_filtered_companies(
                    stage2_filtered_companies['corp_code'].tolist(),
                    TARGET_BSNS_YEAR,
                    TARGET_REPRT_CODE,
                    append=False
                )
                logging.info(f"Stage 1 & 2 completed. {len(stage2_filtered_companies)} companies passed and saved to 'filtered_companies' table.")
            else:
                logging.info("No companies passed Stage 1 & 2. 'filtered_companies' table might be empty.")
            
            if args.stage == '1_2':
                return "" # Return empty string if only stage 1_2 is run and no report is needed here

        if args.stage == '3' or args.stage == 'all':
            logging.info("--- Running Stage 3: Valuation Metrics Check ---")
            companies_for_stage3_df = analyzer._load_filtered_companies_for_stage3(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

            if companies_for_stage3_df.empty:
                logging.info("No companies found in 'filtered_companies' table to apply Stage 3. Make sure Stage 1 & 2 was run first.")
                # Even if no companies are loaded from filtered_companies, we might still want the default message
                # This case is handled by the final check for report_output. 
                # So, we don't return here immediately, but let the empty report_output be handled below.
                pass # Continue to allow handling of empty report_output
            else:
                all_financial_df = analyzer.load_financial_statements(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)
                company_info_df = analyzer.load_company_info()

                filtered_corp_codes = companies_for_stage3_df['corp_code'].unique()
                financial_df_stage3 = all_financial_df[all_financial_df['corp_code'].isin(filtered_corp_codes)]

                if financial_df_stage3.empty:
                    logging.warning("No financial data found for companies loaded for Stage 3.")
                    pass # Continue to allow handling of empty report_output
                else:
                    analysis_df_stage3 = analyzer.calculate_financial_ratios(financial_df_stage3, company_info_df)

                    # Capture Healthy Companies output
                    report_output.append("Healthy Companies:")
                    report_output.append(analysis_df_stage3[['corp_name', 'stock_code', 'PER', 'PBR']].to_string())
                    report_output.append("") # Add a blank line for readability

                    stage3_final_companies_df = analyzer._apply_stage3_filters(analysis_df_stage3)

                    if not stage3_final_companies_df.empty:
                        analyzer.save_filtered_companies(
                            stage3_final_companies_df['corp_code'].tolist(),
                            TARGET_BSNS_YEAR,
                            TARGET_REPRT_CODE,
                            append=False
                        )
                        # Capture Undervalued Companies output
                        report_output.append("Undervalued Companies:")
                        display_df = stage3_final_companies_df[['corp_name', 'stock_code', 'ROE', 'ROA', 'D_E_Ratio', 'Current_Ratio', 'Operating_Cash_Flow', 'PER', 'PBR']].copy()
                        for col in ['ROE', 'ROA', 'D_E_Ratio', 'Current_Ratio', 'Operating_Cash_Flow', 'PER', 'PBR']:
                            display_df[col] = pd.to_numeric(display_df[col], errors='coerce')
                            display_df[col] = display_df[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else 'N/A')
                        report_output.append(display_df.to_string())
                        
                        logging.info(f"\nStage 3 completed. {len(stage3_final_companies_df)} companies passed all stages and saved to 'filtered_companies' table.")
                    else:
                        logging.info("No undervalued companies found based on Stage 3 criteria.")

    except FileNotFoundError as e:
        logging.error(e)
        return "" # Return empty string on error
    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}")
        return "" # Return empty string on error
    
    # If no companies were found for reporting, generate the default message
    if not report_output:
        return f"No companies detected as healthy nor undervalued for {TARGET_BSNS_YEAR} {display_quarter}."
    
    return "\n".join(report_output)

if __name__ == "__main__":
    print(main())
