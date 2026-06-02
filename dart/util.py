import os
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import time
import logging
from dotenv import load_dotenv # Keep for loading DART_API_KEY if needed by other DART functions
import zipfile
import io
import json

def _get_reporting_period_end_date(bsns_year, reprt_code):
    """
    Determines the estimated end date of the reporting period based on bsns_year and reprt_code.
    Returns date in 'YYYYMMDD' format.
    """
    if reprt_code == '11011':  # Q4/Annual
        return f"{bsns_year}1231"
    elif reprt_code == '11014': # Q3
        return f"{bsns_year}0930"
    elif reprt_code == '11012': # Q2
        return f"{bsns_year}0630"
    elif reprt_code == '11013': # Q1
        return f"{bsns_year}0331"
    else:
        logging.warning(f"Unknown reprt_code: {reprt_code}. Returning end of year as default.")
        return f"{bsns_year}1231"


def get_display_quarter_from_report_code(reprt_code):
    if reprt_code == '11011': return 'Annual'
    elif reprt_code == '11014': return 'Q3'
    elif reprt_code == '11012': return 'Q2'
    elif reprt_code == '11013': return 'Q1'
    else: return 'Unknown Quarter'

def _parse_xml_response(xml_string, root_tag, item_tag):
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
                for expected_tag in ['corp_code', 'corp_name', 'stock_code', 'modify_date']:
                    element = item.find(expected_tag)
                    if element is None:
                        logging.warning(f"CORPCODE.xml parsing: Tag '{expected_tag}' not found for an item.")

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
            return [data]
    except json.JSONDecodeError as e:
        logging.error(f"JSON Parse Error for {root_tag}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error processing JSON for {root_tag}: {e}")
        return None

def determine_recent_report_code_and_year(current_date):
    year = current_date.year

    reporting_periods = [
        (datetime(year, 11, 14).date(), '11014', 'Q3', 0),
        (datetime(year, 8, 14).date(), '11012', 'Q2', 0),
        (datetime(year, 5, 15).date(), '11013', 'Q1', 0),
        (datetime(year, 3, 31).date(), '11011', 'Q4', 1)
    ]

    for deadline_date, r_code, q_display, year_offset in reporting_periods:
        if current_date.date() >= deadline_date:
            return year - year_offset, r_code, q_display

    return year - 1, '11014', 'Q3'

def get_corp_codes(api_key, db_path):
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
        logging.debug(f"DART API Response Text (first 500 chars): {response.text[:500]}...")

        xml_content = None
        if response.headers.get('Content-Type') == 'application/zip' or response.content.startswith(b'PK'):
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    with z.open('CORPCODE.xml') as corpcode_xml:
                        xml_content = corpcode_xml.read().decode('utf-8')
                        logging.info("Successfully extracted CORPCODE.xml from ZIP response.")
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
            corp_codes_df = corp_codes_df.rename(columns={'corp_code': 'corp_code', 'corp_name': 'corp_name', 'stock_code': 'stock_code', 'modify_date': 'modify_date'})
            corp_codes_df['stock_code'] = corp_codes_df['stock_code'].str.strip()
            
            initial_rows = len(corp_codes_df)
            corp_codes_df = corp_codes_df[corp_codes_df['corp_code'].notna() & (corp_codes_df['corp_code'] != '')]
            if len(corp_codes_df) < initial_rows:
                logging.warning(f"Filtered out {initial_rows - len(corp_codes_df)} company_info records due to missing or empty corp_code.")
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
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
    financial_data_dfs = []

    for fs_div_attempt in ['CFS', 'OFS']:
        url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json" if fs_div_attempt == 'CFS' else "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
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

            data = _parse_json_response(response.text, f'fnlttAcnt ({fs_div_attempt})')
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

    return pd.DataFrame()

def _clean_financial_df(df):
    if df.empty:
        return df

    cols_to_keep = [
        'rcept_no', 'bsns_year', 'corp_code', 'stock_code', 'reprt_code',
        'sj_div', 'fs_div', 'fs_nm', 'sj_nm', 'account_id', 'account_nm',
        'thstrm_amount',
        'thstrm_add_amount', 'currency'
    ]
    
    df = df.reindex(columns=cols_to_keep, fill_value='')

    numeric_cols = [
        'bsns_year', 'thstrm_amount', 'thstrm_add_amount', 'ord'
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '', regex=False).replace({'None': '0', None: '0'}).fillna('0')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    string_cols = [col for col in cols_to_keep if col not in numeric_cols]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)

    if 'bsns_year' in df.columns:
        df['bsns_year'] = df['bsns_year'].astype(int)

    return df

def fetch_outstanding_shares(corp_code, stock_code, bsns_year, reprt_code):
    """
    Placeholder: Fetches outstanding shares (dummy value).
    This function will be replaced by data from a pykrx-specific script.
    """
    logging.info(f"Returning DUMMY outstanding shares for {corp_code} ({stock_code}). Actual data will be retrieved by a separate KRX script.")
    # Return a dummy value for now. In a real scenario, this would be fetched from DART.
    return pd.DataFrame({
        'corp_code': [corp_code],
        'bsns_year': [bsns_year],
        'reprt_code': [reprt_code],
        'outstanding_shares': [100000000] # A reasonable large dummy number
    })

def get_db_connection(db_path):
    return sqlite3.connect(db_path)

def insert_financial_data(conn, df, table_name):
    if df.empty:
        return

    cursor = conn.cursor()

    if table_name == 'company_info':
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['?' for _ in df.columns])
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
        try:
            for _, row in df.iterrows():
                cursor.execute(insert_sql, tuple(row))
            conn.commit()
            logging.debug(f"Successfully inserted/updated {len(df)} rows into {table_name}.")
        except sqlite3.Error as e:
            logging.error(f"Error inserting into {table_name}: {e}")

    elif table_name == 'financial_statements':
        metadata_cols = ['rcept_no', 'bsns_year', 'corp_code', 'stock_code', 'reprt_code', 'sj_div', 'fs_div', 'fs_nm', 'currency']
        metadata_df = df[metadata_cols].drop_duplicates(subset=['corp_code', 'bsns_year', 'reprt_code', 'sj_div'])
        
        if not metadata_df.empty:
            meta_columns = ', '.join(metadata_df.columns)
            meta_placeholders = ', '.join(['?' for _ in metadata_df.columns])
            meta_insert_sql = f'''
                INSERT INTO statement_metadata ({meta_columns})
                VALUES ({meta_placeholders})
                ON CONFLICT(corp_code, bsns_year, reprt_code, sj_div) DO UPDATE SET
                    rcept_no = EXCLUDED.rcept_no,
                    stock_code = EXCLUDED.stock_code,
                    fs_div = EXCLUDED.fs_div,
                    fs_nm = EXCLUDED.fs_nm,
                    currency = EXCLUDED.currency
            '''
            try:
                for _, row in metadata_df.iterrows():
                    cursor.execute(meta_insert_sql, tuple(row))
                conn.commit()
                logging.debug(f"Successfully inserted/updated {len(metadata_df)} rows into statement_metadata.")
            except sqlite3.Error as e:
                logging.error(f"Error inserting into statement_metadata: {e}")

        item_cols = [
            'corp_code', 'bsns_year', 'reprt_code', 'sj_div', 'account_id', 'account_nm',
            'thstrm_amount', 'thstrm_add_amount'
        ]
        items_df = df[item_cols].copy()

        if not items_df.empty:
            item_columns = ', '.join(items_df.columns)
            item_placeholders = ', '.join(['?' for _ in items_df.columns])
            item_insert_sql = f'''
                INSERT INTO financial_statement_items ({item_columns})
                VALUES ({item_placeholders})
                ON CONFLICT(corp_code, bsns_year, reprt_code, sj_div, account_id) DO UPDATE SET
                    account_nm = EXCLUDED.account_nm,
                    thstrm_amount = EXCLUDED.thstrm_amount,
                    thstrm_add_amount = EXCLUDED.thstrm_add_amount
            '''
            try:
                for _, row in items_df.iterrows():
                    cursor.execute(item_insert_sql, tuple(row))
                conn.commit()
                logging.debug(f"Successfully inserted/updated {len(items_df)} rows into financial_statement_items.")
            except sqlite3.Error as e:
                logging.error(f"Error inserting into financial_statement_items: {e}")

    elif table_name == 'outstanding_shares':
        if df.empty:
            return
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['?' for _ in df.columns])
        insert_sql = f'''
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
            ON CONFLICT(corp_code, bsns_year, reprt_code) DO UPDATE SET
                outstanding_shares = EXCLUDED.outstanding_shares
        '''
        try:
            for _, row in df.iterrows():
                cursor.execute(insert_sql, tuple(row))
            conn.commit()
            logging.debug(f"Successfully inserted/updated {len(df)} rows into {table_name}.")
        except sqlite3.Error as e:
            logging.error(f"Error inserting into {table_name}: {e}")

    elif table_name == 'stock_prices':
        if df.empty:
            return
        columns = ', '.join(df.columns)
        placeholders = ', '.join(['?' for _ in df.columns])
        insert_sql = f'''
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
            ON CONFLICT(stock_code, trade_date) DO UPDATE SET
                close_price = EXCLUDED.close_price
        '''
        try:
            for _, row in df.iterrows():
                cursor.execute(insert_sql, tuple(row))
            conn.commit()
            logging.debug(f"Successfully inserted/updated {len(df)} rows into {table_name}.")
        except sqlite3.Error as e:
            logging.error(f"Error inserting into {table_name}: {e}")

    else:
        logging.warning(f"Unknown table_name: {table_name}. Data not inserted.")

def init_db(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
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
            CREATE TABLE IF NOT EXISTS statement_metadata (
                rcept_no TEXT,
                bsns_year INTEGER,
                corp_code TEXT,
                stock_code TEXT,
                reprt_code TEXT,
                sj_div TEXT,
                fs_div TEXT,
                fs_nm TEXT,
                currency TEXT,
                PRIMARY KEY (corp_code, bsns_year, reprt_code, sj_div)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS financial_statement_items (
                corp_code TEXT,
                bsns_year INTEGER,
                reprt_code TEXT,
                sj_div TEXT,
                account_id TEXT,
                account_nm TEXT,
                thstrm_amount INTEGER,
                thstrm_add_amount INTEGER,
                PRIMARY KEY (corp_code, bsns_year, reprt_code, sj_div, account_id),
                FOREIGN KEY (corp_code, bsns_year, reprt_code, sj_div) REFERENCES statement_metadata(corp_code, bsns_year, reprt_code, sj_div)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outstanding_shares (
                corp_code TEXT,
                bsns_year INTEGER,
                reprt_code TEXT,
                outstanding_shares INTEGER,
                PRIMARY KEY (corp_code, bsns_year, reprt_code),
                FOREIGN KEY (corp_code, bsns_year, reprt_code) REFERENCES statement_metadata(corp_code, bsns_year, reprt_code)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_prices (
                stock_code TEXT,
                trade_date TEXT,
                close_price INTEGER,
                PRIMARY KEY (stock_code, trade_date),
                FOREIGN KEY (stock_code) REFERENCES company_info(stock_code)
            )
        ''')
        conn.commit()
        logging.info("Database tables checked/created successfully.")
    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        raise
    finally:
        if conn:
            conn.close()


def delete_old_financial_data(db_path, bsns_year, reprt_code):
    """
    Deletes old financial data for a specific business year and report code from the database.
    This now targets the new 'statement_metadata' and 'financial_statement_items' tables.
    """
    tables_to_clean = ['financial_statement_items', 'statement_metadata'] # Order matters if no cascade delete

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Delete from financial_statement_items based on bsns_year and reprt_code
            cursor.execute(f"""
                DELETE FROM financial_statement_items
                WHERE bsns_year = ? AND reprt_code = ?
            """, (bsns_year, reprt_code))
            
            # Then, delete from statement_metadata
            cursor.execute(f"DELETE FROM statement_metadata WHERE bsns_year = ? AND reprt_code = ?", (bsns_year, reprt_code))
            
            conn.commit()
            logging.info(f"Cleaned old data for year {bsns_year} and report code {reprt_code} from tables: {', '.join(tables_to_clean)}")
    except sqlite3.Error as e:
        logging.error(f"SQLite error during data cleanup: {e}")
    except Exception as e:
        logging.error(f"Error cleaning old financial data: {e}")
