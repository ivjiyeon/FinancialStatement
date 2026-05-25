import os
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import time
import logging
from dotenv import load_dotenv
import zipfile
import io
import json

def _parse_xml_response(xml_string, root_tag, item_tag):
    """Parses XML response from DART API and returns a list of dictionaries."""
    data = []
    try:
        root = ET.fromstring(xml_string)
        
        if root_tag != 'corpCode': # Conditional check for corpCode.xml
            status = root.find('status').text
            message = root.find('message').text
            
            if status != '000':
                logging.error(f"DART API Error ({root_tag}): Status - {status}, Message - {message}")
                return None

        for item in root.findall(item_tag):
            row = {}
            if root_tag == 'corpCode':
                # Detailed logging for corpCode parsing to identify NoneType errors
                for expected_tag in ['corp_code', 'corp_name', 'stock_code', 'modify_date']:
                    element = item.find(expected_tag)
                    if element is None:
                        logging.warning(f"CORPCODE.xml parsing: Tag '{expected_tag}' not found for an item.")
                    # Removed logging for existing elements to reduce log verbosity, focusing on missing elements
                    # else:
                    #     logging.debug(f"CORPCODE.xml parsing: Found '{expected_tag}' with value '{element.text}'")

            for child in item:
                row[child.tag] = child.text
            data.append(row)
    except ET.ParseError as e:
        logging.error(f"XML Parse Error for {root_tag}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error processing XML for {root_tag}: {e}")
        return None
    return data

def _parse_json_response(json_string, root_tag):
    """Parses JSON response from DART API and returns a list of dictionaries."""
    try:
        data = json.loads(json_string)
        
        status = data.get('status')
        message = data.get('message')

        if status and status != '000':
            logging.error(f"DART API Error ({root_tag}): Status - {status}, Message - {message}")
            return None
            
        if 'list' in data:
            return data['list']
        else:
            # Handle cases where the main data is directly under the root
            return [data] # Wrap in a list for consistent processing if it's a single object
    except json.JSONDecodeError as e:
        logging.error(f"JSON Parse Error for {root_tag}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error processing JSON for {root_tag}: {e}")
        return None

def determine_recent_report_code_and_year(current_date):
    """
    Determines the most recently available completed financial statement's
    reporting year, report code, and display quarter based on the current date.
    """
    year = current_date.year

    reporting_periods = [
        # (deadline_date, report_code, display_quarter, year_offset_for_report)
        # Ordered from latest deadline to earliest to find the most recent available report.
        (datetime(year, 11, 14).date(), '11014', 'Q3', 0),  # Q3 report for current year, due Nov 14
        (datetime(year, 8, 14).date(), '11012', 'Q2', 0),   # Q2 report for current year, due Aug 14
        (datetime(year, 5, 15).date(), '11013', 'Q1', 0),   # Q1 report for current year, due May 15
        (datetime(year, 3, 31).date(), '11011', 'Q4', 1)    # Q4 report for *previous* year, due Mar 31 of current year
    ]

    for deadline_date, r_code, q_display, year_offset in reporting_periods:
        if current_date.date() >= deadline_date:
            return year - year_offset, r_code, q_display

    # If current_date is before March 31 of the current year,
    # the Q4 report of the previous year is not yet due.
    # In this case, the most recently completed and available report would be Q3 of the *previous* year.
    return year - 1, '11014', 'Q3'


def get_corp_codes(api_key, db_path):
    """Fetches all company codes from DART API and updates the company_info table."""
    logging.info("Fetching corporate codes from DART API...")
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': api_key}
    
    try:
        response = None
        logging.debug(f"Requesting URL: {url} with params: {params}")
        response = requests.get(url, params=params, timeout=30)

        response.raise_for_status()

        logging.debug(f"DART API Response Status Code: {response.status_code}")
        logging.debug(f"DART API Response Content-Type: {response.headers.get('Content-Type')}")
        logging.debug(f"DART API Response Text (first 500 chars): {response.text[:500]}...") # Log first 500 chars for brevity

        xml_content = None
        # Check if the response is a ZIP file
        if response.headers.get('Content-Type') == 'application/zip' or response.content.startswith(b'PK'):
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    with z.open('CORPCODE.xml') as corpcode_xml:
                        xml_content = corpcode_xml.read().decode('utf-8')
                        logging.info("Successfully extracted CORPCODE.xml from ZIP response.")
                        # Save the extracted XML to a temporary file for debugging
                        temp_xml_path = "/tmp/CORPCODE_extracted.xml"
                        with open(temp_xml_path, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                        logging.info(f"Saved extracted CORPCODE.xml to {temp_xml_path}")
            except zipfile.BadZipFile:
                logging.error("Received a malformed ZIP file.")
                return pd.DataFrame()
            except KeyError:
                logging.error("CORPCODE.xml not found in the ZIP archive.")
                return pd.DataFrame()
        else:
            xml_content = response.text

        if not xml_content:
            logging.error("No XML content to parse after processing response.")
            return pd.DataFrame()
        
        corp_codes_data = _parse_xml_response(xml_content, 'corpCode', 'list')
        
        if corp_codes_data:
            corp_codes_df = pd.DataFrame(corp_codes_data)
            # Ensure column names match DB schema
            corp_codes_df = corp_codes_df.rename(columns={'corp_code': 'corp_code', 'corp_name': 'corp_name', 'stock_code': 'stock_code', 'modify_date': 'modify_date'})
            corp_codes_df['stock_code'] = corp_codes_df['stock_code'].str.strip() # Clean stock codes
            #corp_codes_df['corp_eng_name'] = '' # Add corp_eng_name with empty string as it's not in XML
            
            # IMPORTANT: Filter out rows with empty or None corp_code BEFORE insertion
            initial_rows = len(corp_codes_df)
            corp_codes_df = corp_codes_df[corp_codes_df['corp_code'].notna() & (corp_codes_df['corp_code'] != '')]
            if len(corp_codes_df) < initial_rows:
                logging.warning(f"Filtered out {initial_rows - len(corp_codes_df)} company_info records due to missing or empty corp_code.")
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Create table if it doesn't exist (already handled by init_db but good for safety)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS company_info (
                        corp_code TEXT PRIMARY KEY,
                        corp_name TEXT,
                        stock_code TEXT,
                        modify_date TEXT,
                        corp_eng_name TEXT
                    )
                ''')
                
                insert_financial_data(conn, corp_codes_df, 'company_info')
                
                logging.info(f"Successfully updated company_info table with {len(corp_codes_df)} corporate codes.")
            return corp_codes_df
        else:
            logging.error("Failed to get corporate codes data from DART API.")
            return pd.DataFrame()
            
    except requests.exceptions.RequestException as e:
        if response is not None:
            logging.error(f"Request error fetching corporate codes: {e}. Status Code: {response.status_code}, Response Text: {response.text}")
        else:
            logging.error(f"Request error fetching corporate codes: {e}. No response received.")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching corporate codes: {e}")
        return pd.DataFrame()
    
def fetch_financial_statements(api_key, corp_code, bsns_year, reprt_code):
    """
    Fetches financial statements (consolidated or separate) from DART API.
    Prioritizes consolidated ('CFS'), falls back to separate ('OFS') if 'CFS' fails or no data.
    """
    financial_data_dfs = []

    for fs_div_attempt in ['CFS', 'OFS']:
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json" if fs_div_attempt == 'CFS' else "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json" # Changed to .json
        params = {
            'crtfc_key': api_key,
            'corp_code': corp_code,
            'bsns_year': bsns_year,
            'reprt_code': reprt_code,
            'fs_div': fs_div_attempt
        }

        logging.debug(f"Attempting to fetch {fs_div_attempt} financial statements for {corp_code} year {bsns_year} report {reprt_code}")
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = _parse_json_response(response.text, f'fnlttAcnt ({fs_div_attempt})') # Use JSON parser
            if data:
                df = pd.DataFrame(data)
                df['fs_div'] = fs_div_attempt
                financial_data_dfs.append(df)
                logging.debug(f"Successfully fetched {len(df)} {fs_div_attempt} financial statement items for {corp_code}.")
                return pd.concat(financial_data_dfs, ignore_index=True)
            else:
                logging.info(f"No {fs_div_attempt} financial statements found for {corp_code}. Trying next fs_div if available.")

        except requests.exceptions.RequestException as e:
            logging.warning(f"{fs_div_attempt} statement request failed for {corp_code}: {e}. Trying next fs_div if available.")
        except Exception as e:
            logging.warning(f"Error processing {fs_div_attempt} statements for {corp_code}: {e}. Trying next fs_div if available.")

    return pd.DataFrame() # Return empty DataFrame if both fail

def _clean_financial_df(df):
    """Cleans and converts financial DataFrame columns to appropriate types."""
    if df.empty:
        return df

    # Define columns to keep based on the financial_statements table schema
    cols_to_keep = [
        'rcept_no', 'bsns_year', 'corp_code', 'stock_code', 'reprt_code', 
        'sj_div', 'fs_div', 'fs_nm', 'sj_nm', 'account_id', 'account_nm',
        'account_detail', 'thstrm_nm', 'thstrm_dt', 'thstrm_amount',
        'thstrm_add_amount', 'ord', 'currency'
    ]
    
    # Filter DataFrame to keep only relevant columns
    df = df.reindex(columns=cols_to_keep, fill_value='')

    # Columns expected to be numeric
    numeric_cols = [
        'bsns_year', 'thstrm_amount', 'thstrm_add_amount', 'ord'
    ]
    for col in numeric_cols:
        if col in df.columns:
            # Convert 'None' strings or actual None/NaN to 0 before converting to numeric
            df[col] = df[col].astype(str).str.replace(',', '', regex=False).replace({'None': '0', None: '0'}).fillna('0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # Columns expected to be string (all others in cols_to_keep)
    string_cols = [col for col in cols_to_keep if col not in numeric_cols]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)

    # Ensure bsns_year is integer (already handled by numeric_cols, but good for explicit check)
    if 'bsns_year' in df.columns:
        df['bsns_year'] = df['bsns_year'].astype(int)

    return df


def get_db_connection(db_path):
    """Establishes a database connection."""
    return sqlite3.connect(db_path)

def insert_financial_data(conn, df, table_name):
    """Inserts or updates financial data into the specified table."""
    if df.empty:
        return

    cursor = conn.cursor()

    # If inserting into financial statement tables, check if the report already exists
    if table_name == 'financial_statements':
        if not df.empty:
            sample_row = df.iloc[0]
            corp_code = sample_row['corp_code']
            bsns_year = int(sample_row['bsns_year']) # Ensure bsns_year is integer for comparison
            reprt_code = sample_row['reprt_code']
            sj_div = sample_row['sj_div']
            # For combined financial_statements table, primary key check includes sj_div

            # Check if any record with this combination already exists
            cursor.execute(f"""
                SELECT 1 FROM financial_statements
                WHERE corp_code = ? AND bsns_year = ? AND reprt_code = ? AND sj_div = ?
                LIMIT 1
            """, (corp_code, bsns_year, reprt_code, sj_div))
            
            if cursor.fetchone():
                logging.info(f"Skipping insertion for {corp_code}, year {bsns_year}, report {reprt_code}, sj_div {sj_div} in financial_statements as it already exists.")
                return # Skip insertion for this entire report

    columns = ', '.join(df.columns)
    placeholders = ', '.join(['?' for _ in df.columns])

    # Construct the ON CONFLICT clause for UPSERT (INSERT OR REPLACE)
    # Assuming the PRIMARY KEY for financial tables is (corp_code, bsns_year, reprt_code, sj_div, account_id)
    # This will replace existing rows with the same primary key.
    
    if table_name == 'company_info':
         insert_sql = f'''
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
            ON CONFLICT(corp_code) DO UPDATE SET
                corp_code = EXCLUDED.corp_code,
                corp_name = EXCLUDED.corp_name,
                stock_code = EXCLUDED.stock_code,
                modify_date = EXCLUDED.modify_date,
                corp_eng_name = EXCLUDED.corp_eng_name
        '''
    else: # financial_statements
        insert_sql = f'''
            INSERT INTO financial_statements ({columns})
            VALUES ({placeholders})
            ON CONFLICT(corp_code, bsns_year, reprt_code, sj_div, account_id) DO UPDATE SET
                rcept_no = EXCLUDED.rcept_no,
                fs_div = EXCLUDED.fs_div,
                fs_nm = EXCLUDED.fs_nm,
                sj_nm = EXCLUDED.sj_nm,
                account_nm = EXCLUDED.account_nm,
                account_detail = EXCLUDED.account_detail,
                thstrm_nm = EXCLUDED.thstrm_nm,
                thstrm_dt = EXCLUDED.thstrm_dt,
                thstrm_amount = EXCLUDED.thstrm_amount,
                thstrm_add_amount = EXCLUDED.thstrm_add_amount,
                ord = EXCLUDED.ord,
                currency = EXCLUDED.currency
        '''
    
    try:
        for _, row in df.iterrows():
            cursor.execute(insert_sql, tuple(row))
        conn.commit()
        logging.debug(f"Successfully inserted/updated {len(df)} rows into {table_name}.")
    except sqlite3.Error as e:
        logging.error(f"Error inserting into {table_name}: {e}")

def init_db(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Create company_info table if it doesn't exist (if not already created by another script)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_info (
                corp_code TEXT PRIMARY KEY,
                corp_name TEXT,
                stock_code TEXT,
                modify_date TEXT,
                corp_eng_name TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_statements (
                rcept_no TEXT,
                bsns_year INTEGER,
                corp_code TEXT,
                stock_code TEXT,
                reprt_code TEXT,
                sj_div TEXT,
                fs_div TEXT,         -- Financial Statement division (e.g., 'CFS', 'OFS')
                fs_nm TEXT,
                sj_nm TEXT,
                account_id TEXT,
                account_nm TEXT,
                account_detail TEXT,
                thstrm_nm TEXT,
                thstrm_dt TEXT,
                thstrm_amount INTEGER,
                thstrm_add_amount INTEGER,
                ord INTEGER,
                currency TEXT,
                PRIMARY KEY (corp_code, bsns_year, reprt_code, sj_div, account_id)
            )
        ''')
        conn.commit()
        logging.info("Database tables checked/created successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        raise # Re-raise to stop execution if DB init fails
    finally:
        if conn:
            conn.close()
