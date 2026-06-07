import sys
import os
import sqlite3
import pandas as pd
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv


# Dynamically add the project root to sys.path
# This assumes the script is in a subdirectory like 'scripts/'
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = os.path.join(PROJECT_ROOT, 'scripts/analyze_and_identify_undervalued.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv(dotenv_path=PROJECT_ROOT / '.env')
sys.path.append(str(PROJECT_ROOT))


class FinancialAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path
        #self.project_root = Path(__file__).resolve().parents[1]
        #self.venv_krx_python = self.project_root / 'venv_krx' / 'bin' / 'python'
        #self.venv_dart_python = self.project_root / 'venv_dart' / 'bin' / 'python'
        if not os.path.exists(self.db_path):
            logging.error(f"Database not found at {self.db_path}")
            raise FileNotFoundError(f"Database not found at {self.db_path}")

    def _get_db_connection(self):
        return sqlite3.connect(self.db_path)

    def load_company_info(self):
        logging.debug("Loading company information...")
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
        logging.debug(f"Loading financial statements for year {bsns_year}, report {reprt_code}...")
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
                    fsi.thstrm_amount,
                    fsi.thstrm_add_amount
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
                'thstrm_amount': 'float32',
                'thstrm_add_amount': 'float32'
            })
        logging.info(f"Loaded {len(financial_df)} financial statement records.")
        return financial_df

    def load_outstanding_shares(self):
        logging.debug("Loading all outstanding shares...")
        with self._get_db_connection() as conn:
            query = """
                SELECT
                    corp_code,
                    trade_date,
                    outstanding_shares
                FROM outstanding_shares_data
            """
            shares_df = pd.read_sql_query(query, conn, dtype={
                'corp_code': str,
                'trade_date': str,
                'outstanding_shares': 'int64'
            })
        logging.info(f"Loaded {len(shares_df)} outstanding shares records.")
        return shares_df

    def load_stock_prices(self):
        logging.debug(f"Loading all stock prices...")
        with self._get_db_connection() as conn:
            query = """
                SELECT
                    stock_code,
                    trade_date,
                    close_price
                FROM stock_prices_data
            """
            prices_df = pd.read_sql_query(query, conn, dtype={
                'stock_code': str,
                'trade_date': str,
                'close_price': 'int64'
            })
        logging.info(f"Loaded {len(prices_df)} stock price records.")
        return prices_df

    def load_krx_sector_data(self):
        logging.debug("Loading KRX sector data...")
        krx_sector_path = PROJECT_ROOT / 'data' / 'krx_sector_data.csv'
        if not krx_sector_path.exists():
            logging.error(f"KRX sector data not found at {krx_sector_path}")
            return pd.DataFrame()
        krx_sector_df = pd.read_csv(krx_sector_path, dtype={'Stock Code': str})
        krx_sector_df = krx_sector_df.rename(columns={'Stock Code': 'stock_code', 'Sector Classification': 'Sector'})
        logging.info(f"Loaded {len(krx_sector_df)} KRX sector records.")
        return krx_sector_df

    def _calculate_base_ratios(self, financial_df, company_info_df, krx_sector_df=None):
        logging.debug("Calculating base financial ratios...")
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

        # Merge with KRX sector data
        if krx_sector_df is not None and not krx_sector_df.empty:
            merged_df = pd.merge(merged_df, krx_sector_df[['stock_code', 'Sector']], on='stock_code', how='left')
            merged_df['Sector'] = merged_df['Sector'].fillna('Unknown')

        # Initialize ratio columns with 0.0 or None
        ratio_cols = ['Total_Assets', 'Total_Equity', 'Total_Liabilities', 'Current_Assets', 'Current_Liabilities', 
                    'Net_Income', 'Operating_Cash_Flow', 'D_E_Ratio', 'Current_Ratio', 'ROE', 'ROA']
        
        for col in ratio_cols:
            if col not in merged_df.columns:
                merged_df[col] = pd.NA

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
        merged_df['D_E_Ratio'] = merged_df['D_E_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # Current Ratio
        merged_df['Current_Ratio'] = merged_df['Current_Assets'] / merged_df['Current_Liabilities']
        merged_df['Current_Ratio'] = merged_df['Current_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # ROE (Return on Equity)
        merged_df['ROE'] = merged_df['Net_Income'] / merged_df['Total_Equity']
        merged_df['ROE'] = merged_df['ROE'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # ROA (Return on Assets)
        merged_df['ROA'] = merged_df['Net_Income'] / merged_df['Total_Assets']
        merged_df['ROA'] = merged_df['ROA'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)
        
        logging.info("Base financial ratios calculated.")
        return merged_df

    def _calculate_valuation_ratios(self, analysis_df, financial_df, outstanding_shares_df, stock_prices_df):
        logging.debug("Calculating valuation ratios (PER, PBR, EPS, BPS)...")
        if analysis_df.empty:
            logging.warning("Analysis DataFrame is empty, cannot calculate valuation ratios.")
            return pd.DataFrame()

        # Merge with outstanding shares
        logging.debug(f"Before merging outstanding_shares_df: analysis_df shape {analysis_df.shape}, outstanding_shares_df shape {outstanding_shares_df.shape}")
        analysis_df = pd.merge(analysis_df, outstanding_shares_df[['corp_code', 'outstanding_shares']], on='corp_code', how='left')
        logging.debug(f"After merging outstanding_shares_df: analysis_df shape {analysis_df.shape}")
        logging.debug(f"NaNs in 'outstanding_shares' after merge: {analysis_df['outstanding_shares'].isnull().sum()}")
        analysis_df['outstanding_shares'] = analysis_df['outstanding_shares'].fillna(pd.NA)

        # Merge with stock prices
        logging.debug(f"Before merging stock_prices_df: analysis_df shape {analysis_df.shape}, stock_prices_df shape {stock_prices_df.shape}")
        analysis_df = pd.merge(analysis_df, stock_prices_df[['stock_code', 'close_price']], on='stock_code', how='left')
        logging.debug(f"After merging stock_prices_df: analysis_df shape {analysis_df.shape}")
        logging.debug(f"NaNs in 'close_price' after merge: {analysis_df['close_price'].isnull().sum()}")
        analysis_df['close_price'] = analysis_df['close_price'].fillna(pd.NA)

        # Initialize valuation ratio columns
        valuation_ratio_cols = ['EPS', 'BPS', 'PER', 'PBR']
        for col in valuation_ratio_cols:
            if col not in analysis_df.columns:
                analysis_df[col] = pd.NA

        logging.info("Calculating PER, PBR, EPS, and BPS using vectorized operations...")
        # Calculate EPS: Net Income / Outstanding Shares * 4 (annualized assuming quarterly data)
        # Need to ensure Net_Income is properly adjusted for annual reports based on Q3 thstrm_add_amount if applicable

        # Get thstrm_add_amount for ProfitLoss for current bsns_year and Q3 (11014) report code
        # This requires access to the full financial_df including thstrm_add_amount, which is now available.
        q3_add_amounts = financial_df[
            (financial_df['account_id'] == 'ifrs-full_ProfitLoss') &
            (financial_df['reprt_code'] == '11014') &
            (financial_df['sj_div'].isin(['IS', 'CIS']))
        ][['corp_code', 'bsns_year', 'thstrm_add_amount']].drop_duplicates()

        # Merge Q3 additional amounts to analysis_df
        analysis_df = pd.merge(
            analysis_df,
            q3_add_amounts.rename(columns={'thstrm_add_amount': 'Q3_ProfitLoss_Add_Amount'}),
            on=['corp_code', 'bsns_year'],
            how='left'
        )
        analysis_df['Q3_ProfitLoss_Add_Amount'] = analysis_df['Q3_ProfitLoss_Add_Amount'].fillna(0)

        # Adjust Net_Income for annual reports (reprt_code '11011') by subtracting Q3 additional amount
        annual_report_mask = analysis_df['reprt_code'] == '11011'
        analysis_df.loc[annual_report_mask, 'Net_Income_Adjusted'] = \
            analysis_df.loc[annual_report_mask, 'Net_Income'] - analysis_df.loc[annual_report_mask, 'Q3_ProfitLoss_Add_Amount']
        analysis_df['Net_Income_Adjusted'] = analysis_df['Net_Income_Adjusted'].fillna(analysis_df['Net_Income'])

        # Calculate EPS: Net Income / Outstanding Shares * 4 (annualized assuming quarterly data)
        # Check for valid outstanding_shares before calculating EPS and BPS
        analysis_df['EPS'] = analysis_df.apply(lambda row: 
            row['Net_Income_Adjusted'] / row['outstanding_shares'] * 4 
            if pd.notna(row['outstanding_shares']) and row['outstanding_shares'] != 0 
            else pd.NA, axis=1
        )
        analysis_df['BPS'] = analysis_df.apply(lambda row: 
            row['Total_Equity'] / row['outstanding_shares'] 
            if pd.notna(row['outstanding_shares']) and row['outstanding_shares'] != 0 
            else pd.NA, axis=1
        )

        # Handle division by zero or NaN for EPS and BPS
        analysis_df['EPS'] = analysis_df['EPS'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)
        analysis_df['BPS'] = analysis_df['BPS'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)

        # Calculate PER (Price / EPS)
        analysis_df['PER'] = analysis_df['close_price'] / analysis_df['EPS']
        analysis_df['PER'] = analysis_df['PER'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)
        # Ensure PER is not negative if EPS is negative
        analysis_df.loc[analysis_df['EPS'] < 0, 'PER'] = pd.NA

        # Calculate PBR (Price / BPS)
        analysis_df['PBR'] = analysis_df['close_price'] / analysis_df['BPS']
        analysis_df['PBR'] = analysis_df['PBR'].replace([float('inf'), -float('inf')], pd.NA).fillna(pd.NA)
        # Ensure PBR is not negative if BPS is negative
        analysis_df.loc[analysis_df['BPS'] < 0, 'PBR'] = pd.NA

        # Drop the temporary Net_Income_Adjusted column
        analysis_df = analysis_df.drop(columns=['Net_Income_Adjusted', 'Q3_ProfitLoss_Add_Amount'], errors='ignore')
        
        logging.info("Valuation ratios calculated.")
        return analysis_df

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
            """
            )
            conn.commit()

            insert_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data_to_insert = [(corp_code, int(bsns_year), reprt_code, insert_date) for corp_code in corp_codes]
            cursor.executemany("""
                INSERT OR REPLACE INTO filtered_companies (corp_code, bsns_year, reprt_code, analysis_date)
                VALUES (?, ?, ?, ?)
            """, data_to_insert)
            conn.commit()
        logging.info("Filtered companies saved successfully.")

    def get_filtered_companies(self, bsns_year, reprt_code):
        logging.info(f"Fetching filtered companies for {bsns_year}-{reprt_code} from database (raw SQL)...")
        companies = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT DISTINCT fc.corp_code, ci.stock_code, fc.bsns_year, fc.reprt_code
                    FROM filtered_companies AS fc
                    JOIN company_info AS ci ON fc.corp_code = ci.corp_code
                    WHERE fc.bsns_year = ? AND fc.reprt_code = ?
                """
                cursor.execute(query, (bsns_year, reprt_code))
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                for row in rows:
                    companies.append(dict(zip(columns, row)))
            logging.info(f"Found {len(companies)} filtered companies (raw SQL).")
        except Exception as e:
            logging.error(f"Error fetching filtered companies (raw SQL): {e}")
        return companies

    def init_new_tables(self):
        """
        Initializes the new tables for stock prices and outstanding shares data.
        """
        logging.info("Initializing new database tables: stock_prices_data and outstanding_shares_data...")
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Drop tables if they exist to ensure a clean start
                cursor.execute('DROP TABLE IF EXISTS stock_prices_data;')
                cursor.execute('DROP TABLE IF EXISTS outstanding_shares_data;')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stock_prices_data (
                        stock_code TEXT NOT NULL,
                        trade_date TEXT NOT NULL,
                        open_price INTEGER,
                        high_price INTEGER,
                        low_price INTEGER,
                        close_price INTEGER,
                        volume INTEGER,
                        PRIMARY KEY (stock_code, trade_date)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS outstanding_shares_data (
                        corp_code TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        trade_date TEXT NOT NULL,
                        outstanding_shares INTEGER,
                        PRIMARY KEY (corp_code, stock_code, trade_date)
                    )
                ''')
                conn.commit()
            logging.info("New tables initialized successfully.")
        except Exception as e:
            logging.error(f"Error initializing new tables: {e}")

    def run_krx_data_fetch_script(self, corp_code: str, stock_code: str, start_date: str, end_date: str, krx_id: str, krx_pw: str) -> bool:
        """
        Executes a separate Python script within venv_krx to fetch KRX data.
        """
        # Use PROJECT_ROOT defined globally and self.db_path
        venv_krx_python = PROJECT_ROOT / 'venv_krx' / 'bin' / 'python'
        script_path = PROJECT_ROOT / 'scripts' / 'krx_data_fetch_worker.py'

        if not os.path.exists(script_path):
            logging.error(f"Krx data fetch worker script not found at {script_path}. Cannot proceed.")
            return False

        command = [
            str(venv_krx_python),
            str(script_path),
            '--corp_code', corp_code,
            '--stock_code', stock_code,
            '--start_date', start_date,
            '--end_date', end_date,
            '--db_path', str(self.db_path)
        ]
        
        subprocess_env = os.environ.copy()
        subprocess_env['KRX_ID'] = krx_id
        subprocess_env['KRX_PW'] = krx_pw

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, env=subprocess_env)
            logging.debug(f"Krx data fetch for {stock_code} completed. Output:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Krx data fetch for {stock_code} failed with error:\n{e.stderr}\n{e.stdout}")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during KRX data fetch for {stock_code}: {e}")
            return False

    def run_dart_data_fetch_script(self, corp_code: str, stock_code: str, bsns_year: int, reprt_code: str, dart_api_key: str) -> bool:
        """
        Executes a separate Python script within venv_dart to fetch DART outstanding shares data.
        """
        # Use PROJECT_ROOT defined globally and self.db_path
        venv_dart_python = PROJECT_ROOT / 'venv_dart' / 'bin' / 'python'
        script_path = PROJECT_ROOT / 'scripts' / 'dart_data_fetch_worker.py'

        if not os.path.exists(script_path):
            logging.error(f"DART data fetch worker script not found at {script_path}. Cannot proceed.")
            return False

        command = [
            str(venv_dart_python),
            str(script_path),
            '--corp_code', corp_code,
            '--stock_code', stock_code,
            '--bsns_year', str(bsns_year),
            '--reprt_code', reprt_code,
            '--db_path', str(self.db_path)
        ]
        
        subprocess_env = os.environ.copy()
        subprocess_env['DART_API_KEY'] = dart_api_key

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, env=subprocess_env)
            logging.debug(f"DART data fetch for {stock_code} completed. Output:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"DART data fetch for {stock_code} failed with error:\n{e.stderr}\n{e.stdout}")
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during DART data fetch for {stock_code}: {e}")
            return False

def main():
    PROJECT_ROOT_DIR = Path('/home/ivjiyeonb/projects/financial_statement/')
    DB_PATH = PROJECT_ROOT_DIR / 'data' / 'financial_data.db'

    TARGET_BSNS_YEAR = os.getenv('TARGET_BSNS_YEAR')
    TARGET_REPRT_CODE = os.getenv('TARGET_REPRT_CODE')

    if not TARGET_BSNS_YEAR or not TARGET_REPRT_CODE:
        logging.error("Error: TARGET_BSNS_YEAR or TARGET_REPRT_CODEenvironment variable is not set.")
        sys.exit(1)

    analyzer = FinancialAnalyzer(DB_PATH)

    # Initialize variables to hold results from processing, to be used in report generation
    processed_stage2_companies_df = pd.DataFrame()
    processed_stage3_companies_df = pd.DataFrame()
    analysis_df = pd.DataFrame() # To store the full analysis df if calculated

    try:
        # Load all common data once
        company_info_df = analyzer.load_company_info()
        financial_df_full = analyzer.load_financial_statements(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)

        # Add checks for Net_Income and Total_Equity in financial_df_full
        if not {'ifrs-full_ProfitLoss', 'ifrs-full_Equity'}.issubset(financial_df_full['account_id'].unique()):
            logging.warning("Warning: 'ifrs-full_ProfitLoss' or 'ifrs-full_Equity' missing from financial_df_full. PBR/EPS might be affected.")

        # Convert 'thstrm_amount' to numeric, coercing errors, then check for NaNs in critical columns
        financial_df_full['thstrm_amount'] = pd.to_numeric(financial_df_full['thstrm_amount'], errors='coerce')
        if financial_df_full[financial_df_full['account_id'] == 'ifrs-full_ProfitLoss']['thstrm_amount'].isnull().any():
            logging.warning("Warning: NaN values found in 'thstrm_amount' for 'ifrs-full_ProfitLoss' in financial_df_full.")
        if financial_df_full[financial_df_full['account_id'] == 'ifrs-full_Equity']['thstrm_amount'].isnull().any():
            logging.warning("Warning: NaN values found in 'thstrm_amount' for 'ifrs-full_Equity' in financial_df_full.")
        krx_sector_df = analyzer.load_krx_sector_data()

        if 'thstrm_amount' not in financial_df_full.columns:
            logging.error("'thstrm_amount' column not found in financial statements, cannot proceed with ratio calculation.")
            return # Exit main if critical data is missing
        
        if krx_sector_df.empty:
            logging.warning("KRX sector data not loaded, proceeding without sector information.")
        
        logging.info("--- Running Stage 1 & 2: Financial Health and Profitability Check ---")

        current_date = datetime.now()

        # Load environment variables for data fetching
        KRX_ID = os.getenv('KRX_ID')
        KRX_PW = os.getenv('KRX_PW')
        DART_API_KEY = os.getenv('DART_API_KEY')

        if not KRX_ID or not KRX_PW:
            logging.error("KRX_ID or KRX_PW environment variables are not set. Please set them in the .env file.")
            return

        if not DART_API_KEY:
            logging.error("DART_API_KEY environment variable is not set. Please set it in the .env file.")
            return

        # --- Step 1: Initial Calculation of Ratios for Stage 1 & 2 Filtering ---
        logging.info("Performing initial ratio calculation for Stage 1 & 2 filtering (base ratios only)...")
        analysis_df = analyzer._calculate_base_ratios(financial_df_full, company_info_df, krx_sector_df)
        processed_stage2_companies_df = analyzer._apply_stage1_and_2_filters(analysis_df)

        if not processed_stage2_companies_df.empty:
            analyzer.save_filtered_companies(
                processed_stage2_companies_df['corp_code'].tolist(),
                TARGET_BSNS_YEAR,
                TARGET_REPRT_CODE,
                append=False
            )
            logging.info(f"Stage 1 & 2 initial filtering completed. {len(processed_stage2_companies_df)} companies passed and saved to 'filtered_companies' table for data fetching.")
        else:
            logging.info("No companies passed Stage 1 & 2 initial filtering. No data will be fetched.")
            analysis_df = pd.DataFrame() # No companies, so no ratios
        
        # --- Step 2: Fetch Data for the Filtered Companies ---
        if not processed_stage2_companies_df.empty:
            analyzer.init_new_tables() # Clear existing stock prices/outstanding shares for a fresh fetch
            
            # Load the newly filtered companies
            filtered_companies_list = analyzer.get_filtered_companies(TARGET_BSNS_YEAR, TARGET_REPRT_CODE)
            
            if filtered_companies_list:
                logging.info(f"Fetching data for {len(filtered_companies_list)} companies...")
                for company_data in filtered_companies_list:
                    corp_code = company_data['corp_code']
                    stock_code = company_data['stock_code']
                    bsns_year_data_fetch = company_data['bsns_year']
                    reprt_code_data_fetch = company_data['reprt_code']
                    
                    logging.info(f"Initiating data fetch for (Stock Code: {stock_code}, Corp Code: {corp_code})...")
                    start_date_krx = (current_date - timedelta(days=7)).strftime('%Y%m%d')
                    end_date_krx = current_date.strftime('%Y%m%d')

                    # Fetch KRX stock prices (OHLCV)
                    logging.info(f"Attempting to fetch KRX stock prices for ({stock_code}) from {start_date_krx} to {end_date_krx}...")
                    try:
                        if analyzer.run_krx_data_fetch_script(corp_code, stock_code, start_date_krx, end_date_krx, KRX_ID, KRX_PW):
                            logging.info(f"Successfully fetched KRX stock prices for ({stock_code}).")
                        else:
                            logging.error(f"Failed to fetch KRX stock prices for ({stock_code}). Check previous logs for details.")
                    except Exception as e:
                        logging.error(f"An error occurred while fetching KRX stock prices for ({stock_code}): {e}")

                    # Fetch DART outstanding shares
                    logging.info(f"Attempting to fetch DART outstanding shares for ({stock_code}) for year {bsns_year_data_fetch}...")
                    try:
                        if analyzer.run_dart_data_fetch_script(corp_code, stock_code, bsns_year_data_fetch, reprt_code_data_fetch, DART_API_KEY):
                            logging.info(f"Successfully fetched DART outstanding shares for ({stock_code}).")
                        else:
                            logging.error(f"Failed to fetch DART outstanding shares for ({stock_code}). Check previous logs for details.")
                    except Exception as e:
                        logging.error(f"An unexpected error occurred during DART data fetch for ({stock_code}): {e}")
            else:
                logging.info("No filtered companies found after re-loading for data fetching. This should not happen if Stage 1&2 passed.")

            # Re-load outstanding shares and stock prices after fetching new data
            outstanding_shares_df = analyzer.load_outstanding_shares()
            stock_prices_df = analyzer.load_stock_prices()

        # --- Stage 3: Valuation Metrics Check ---
        logging.info("--- Running Stage 3: Valuation Metrics Check ---")
        
        companies_for_stage3_df = processed_stage2_companies_df.copy()
        if companies_for_stage3_df.empty:
            logging.info("No companies passed Stage 1 & 2, so Stage 3 cannot proceed.")
            processed_stage3_companies_df = pd.DataFrame() # Ensure this is empty
        else:
            processed_stage2_companies_df = analyzer._calculate_valuation_ratios(processed_stage2_companies_df, financial_df_full, outstanding_shares_df, stock_prices_df)
            processed_stage3_companies_df = analyzer._apply_stage3_filters(processed_stage2_companies_df) #analysis_df_stage3)

        if not processed_stage3_companies_df.empty:
            analyzer.save_filtered_companies(
                processed_stage3_companies_df['corp_code'].tolist(),
                TARGET_BSNS_YEAR,
                TARGET_REPRT_CODE,
                append=False
            )
            logging.info(f"Stage 3 completed. {len(processed_stage3_companies_df)} companies passed all stages and saved to 'filtered_companies' table.")
        else:
            logging.info("No undervalued companies found based on Stage 3 criteria.")

        # --- Final Report Assembly ---
        final_report_lines = []

        if not processed_stage2_companies_df.empty:
            final_report_lines.append("Healthy Companies:")
            healthy_companies_cols = ['corp_name', 'stock_code', 'Sector', 'PER', 'PBR', 'EPS', 'BPS']
            display_df_healthy = processed_stage2_companies_df[[col for col in healthy_companies_cols if col in processed_stage2_companies_df.columns]].copy()
            for col in ['PER', 'PBR', 'EPS', 'BPS']:
                if col in display_df_healthy.columns:
                    display_df_healthy[col] = pd.to_numeric(display_df_healthy[col], errors='coerce')
                    display_df_healthy[col] = display_df_healthy[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else 'N/A')
            final_report_lines.append(display_df_healthy.to_string(index=False, col_space=10))
        
        if not processed_stage3_companies_df.empty:
            if final_report_lines: # Add a separator if Healthy Companies section already exists
                final_report_lines.append("") # Ensure a blank line between sections
            final_report_lines.append("Undervalued Companies:")
            undervalued_companies_cols = ['corp_name', 'stock_code', 'ROE', 'ROA', 'PER', 'PBR', 'EPS', 'BPS'] #, 'D_E_Ratio', 'Current_Ratio', 'Operating_Cash_Flow'
            display_df_undervalued = processed_stage3_companies_df[[col for col in undervalued_companies_cols if col in processed_stage3_companies_df.columns]].copy()
            for col in ['ROE', 'ROA', 'PER', 'PBR', 'EPS', 'BPS']: #'D_E_Ratio', 'Current_Ratio', 'Operating_Cash_Flow', 
                if col in display_df_undervalued.columns:
                    display_df_undervalued[col] = pd.to_numeric(display_df_undervalued[col], errors='coerce')
                    display_df_undervalued[col] = display_df_undervalued[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else 'N/A')
            final_report_lines.append(display_df_undervalued.to_string(index=False, col_space=10))


        # If no companies were found in any relevant stage for the requested report type, or if no stages were specified for reporting
        if not final_report_lines:
            print(f"No companies detected as healthy nor undervalued for {TARGET_BSNS_YEAR} {TARGET_REPRT_CODE}.")
        else:
            logging.debug(f"Final report_output content: {final_report_lines}")
            print("\n".join(final_report_lines))

    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
