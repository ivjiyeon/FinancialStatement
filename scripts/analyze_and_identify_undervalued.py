import sqlite3
import pandas as pd
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
            # Select relevant columns for analysis
            query = f"""
                SELECT
                    corp_code,
                    bsns_year,
                    reprt_code,
                    sj_div,
                    fs_div,
                    account_nm,
                    thstrm_amount
                FROM financial_statements
                WHERE bsns_year = {bsns_year} AND reprt_code = '{reprt_code}'
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

    def calculate_financial_ratios(self, financial_df, company_info_df):
        logging.info("Calculating financial ratios...")
        if financial_df.empty:
            logging.warning("Financial DataFrame is empty, cannot calculate ratios.")
            return pd.DataFrame()

        # Pivot the financial data for easier ratio calculation
        # We need to handle potential duplicate account_nm entries for the same corp_code/sj_div
        # For simplicity, let's take the first one if duplicates exist for now.
        financial_pivot = financial_df.pivot_table(index=['corp_code', 'bsns_year', 'reprt_code', 'sj_div', 'fs_div'],
                                                 columns='account_nm', values='thstrm_amount', aggfunc='first').reset_index()
        financial_pivot.columns.name = None # Remove columns name
        del financial_df # Free up memory as financial_df is no longer needed in its original form

        # Merge with company info to get stock_code and corp_name
        # Ensure merge keys are consistent
        company_info_df_processed = company_info_df[['corp_code', 'stock_code', 'corp_name']].drop_duplicates(subset=['corp_code'])
        merged_df = pd.merge(financial_pivot, company_info_df_processed, on='corp_code', how='left')

        # --- Ratio Calculations (Example: simplified for now) ---
        # Note: These are highly simplified and need careful account mapping for accuracy

        # Example: Total Assets (assuming '자산총계' or similar)
        merged_df['Total_Assets'] = 0.0 # Initialize with float
        if '자산총계' in merged_df.columns:
            merged_df['Total_Assets'] = pd.to_numeric(merged_df['자산총계'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '자산총계' not found for Total Assets calculation.")
        
        # Example: Total Equity (assuming '자본총계' or similar)
        merged_df['Total_Equity'] = 0.0 # Initialize with float
        if '자본총계' in merged_df.columns:
            merged_df['Total_Equity'] = pd.to_numeric(merged_df['자본총계'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '자본총계' not found for Total Equity calculation.")

        # Example: Total Liabilities (assuming '부채총계' or similar)
        merged_df['Total_Liabilities'] = 0.0
        if '부채총계' in merged_df.columns:
            merged_df['Total_Liabilities'] = pd.to_numeric(merged_df['부채총계'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '부채총계' not found for Total Liabilities calculation.")

        # Example: Current Assets (assuming '유동자산' or similar)
        merged_df['Current_Assets'] = 0.0
        if '유동자산' in merged_df.columns:
            merged_df['Current_Assets'] = pd.to_numeric(merged_df['유동자산'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '유동자산' not found for Current Assets calculation.")

        # Example: Current Liabilities (assuming '유동부채' or similar)
        merged_df['Current_Liabilities'] = 0.0
        if '유동부채' in merged_df.columns:
            merged_df['Current_Liabilities'] = pd.to_numeric(merged_df['유동부채'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '유동부채' not found for Current Liabilities calculation.")

        # Example: Net Income (assuming '당기순이익' or similar for IS)
        # Initialize with 0.0, then conditionally update for 'IS' rows
        merged_df['Net_Income'] = 0.0
        is_rows = merged_df['sj_div'] == 'IS'
        if '당기순이익' in merged_df.columns:
            merged_df.loc[is_rows, 'Net_Income'] = pd.to_numeric(merged_df.loc[is_rows, '당기순이익'], errors='coerce').fillna(0.0)
        else:
            logging.warning("Account '당기순이익' not found for Net Income calculation.")

        # P/B Ratio (Price to Book Ratio) - Requires Market Price and Book Value Per Share
        # We don't have market price here, so P/B cannot be calculated accurately yet.
        merged_df['PBR'] = None # Placeholder
        
        # ROE (Return on Equity)
        merged_df['ROE'] = merged_df['Net_Income'] / merged_df['Total_Equity']
        merged_df['ROE'] = merged_df['ROE'].replace([float('inf'), -float('inf')], pd.NA).fillna(0) # Handle division by zero

        # ROA (Return on Assets)
        merged_df['ROA'] = merged_df['Net_Income'] / merged_df['Total_Assets']
        merged_df['ROA'] = merged_df['ROA'].replace([float('inf'), -float('inf')], pd.NA).fillna(0) # Handle division by zero

        # D/E Ratio (Debt to Equity Ratio)
        merged_df['D_E_Ratio'] = merged_df['Total_Liabilities'] / merged_df['Total_Equity']
        merged_df['D_E_Ratio'] = merged_df['D_E_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(0) # Handle division by zero

        # Current Ratio
        merged_df['Current_Ratio'] = merged_df['Current_Assets'] / merged_df['Current_Liabilities']
        merged_df['Current_Ratio'] = merged_df['Current_Ratio'].replace([float('inf'), -float('inf')], pd.NA).fillna(0) # Handle division by zero

        # P/E Ratio (Price to Earnings Ratio) - Requires Market Price and EPS
        merged_df['P_E_Ratio'] = None # Placeholder for now, requires market price data

        # 5-Year Average EPS Growth - Requires historical EPS data
        merged_df['EPS_Growth_5Y'] = None # Placeholder for now, requires historical EPS data


        # Filter for relevant sj_divs (BS for Balance Sheet, IS for Income Statement)
        analysis_df = merged_df[(merged_df['sj_div'] == 'BS') | (merged_df['sj_div'] == 'IS')].copy()

        logging.info("Financial ratios calculated.")
        return analysis_df

    def identify_undervalued_companies(self, analysis_df, criteria=None):
        logging.info("Identifying undervalued companies with updated criteria...")
        if analysis_df.empty:
            logging.warning("Analysis DataFrame is empty, cannot identify undervalued companies.")
            return pd.DataFrame()

        undervalued_companies = analysis_df.copy()

        # --- Mandatory Criteria ---
        # P/E > 0 (Currently P_E_Ratio is None, so this will filter out everything if not handled)
        # P/B > 0 (Currently PBR is None, so this will filter out everything if not handled)
        # ROE > 10%

        # Handle None values for P/E and P/B by converting them to a value that fails the > 0 condition
        undervalued_companies['P_E_Ratio_check'] = undervalued_companies['P_E_Ratio'].fillna(-1)
        undervalued_companies['PBR_check'] = undervalued_companies['PBR'].fillna(-1)

        mandatory_conditions = (
            (undervalued_companies['P_E_Ratio_check'] > 0) &
            (undervalued_companies['PBR_check'] > 0) &
            (undervalued_companies['ROE'] > 0.10) # 10%
        )
        
        undervalued_companies = undervalued_companies[mandatory_conditions].copy()

        if undervalued_companies.empty:
            logging.info("No companies met the mandatory undervaluation criteria.")
            return pd.DataFrame()

        # --- Remaining Conditions (at least 3 of these) ---
        # Note: Industry averages are not available in this script, so we will use absolute thresholds for P/E and P/B.
        # Also, EPS_Growth_5Y is None, so it won't contribute to the count of met conditions.

        # Initialize a counter for met conditions
        undervalued_companies['met_conditions_count'] = 0

        # Condition 1: P/E < 15.0
        # If P_E_Ratio is None, this condition will not be met.
        undervalued_companies['met_conditions_count'] += (undervalued_companies['P_E_Ratio_check'] < 15.0).astype(int)

        # Condition 2: P/B < 1.5
        # If PBR is None, this condition will not be met.
        undervalued_companies['met_conditions_count'] += (undervalued_companies['PBR_check'] < 1.5).astype(int)

        # Condition 3: D/E < 1.0
        undervalued_companies['met_conditions_count'] += (undervalued_companies['D_E_Ratio'] < 1.0).astype(int)

        # Condition 4: Current Ratio > 1.5
        undervalued_companies['met_conditions_count'] += (undervalued_companies['Current_Ratio'] > 1.5).astype(int)

        # Condition 5: 5-Year Average EPS Growth > 5.0%
        # Currently EPS_Growth_5Y is None, so this condition will not be met.
        # For now, if it's None, it won't count. If it were a number, it would be:
        # undervalued_companies['met_conditions_count'] += (undervalued_companies['EPS_Growth_5Y'] > 0.05).astype(int)
        
        # Filter for companies that meet at least 3 of the remaining conditions
        undervalued_companies = undervalued_companies[undervalued_companies['met_conditions_count'] >= 3].copy()

        # Drop temporary check columns
        undervalued_companies = undervalued_companies.drop(columns=['P_E_Ratio_check', 'PBR_check', 'met_conditions_count'])

        logging.info(f"Identified {len(undervalued_companies)} potentially undervalued companies based on systematic criteria.")
        return undervalued_companies

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
        undervalued_companies_df = analyzer.identify_undervalued_companies(analysis_df)
        
        if not undervalued_companies_df.empty:
            logging.info("--- Undervalued Companies Identified ---")
            print(undervalued_companies_df[['corp_name', 'stock_code', 'ROE', 'ROA']].to_string())
        else:
            logging.info("No undervalued companies found based on current criteria.")
            
    except FileNotFoundError as e:
        logging.error(e)
    except Exception as e:
        logging.error(f"An error occurred during analysis: {e}")

if __name__ == "__main__":
    main()
