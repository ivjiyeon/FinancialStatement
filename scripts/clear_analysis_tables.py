import sqlite3
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clear_tables(db_path, tables_to_clear):
    """
    Clears specified tables in the SQLite database.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for table_name in tables_to_clear:
                cursor.execute(f"DELETE FROM {table_name}")
                logging.info(f"Cleared all data from table: {table_name}")
            conn.commit()
            logging.info("Successfully cleared specified tables.")
    except sqlite3.Error as e:
        logging.error(f"SQLite error during table clearing: {e}")
    except Exception as e:
        logging.error(f"Error clearing tables: {e}")

if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'financial_data.db')
    
    tables = ['outstanding_shares_data', 'filtered_companies', 'stock_prices_data']
    
    logging.info(f"Starting to clear tables: {tables} in {DB_PATH}")
    clear_tables(DB_PATH, tables)
    logging.info("Table clearing process completed.")
