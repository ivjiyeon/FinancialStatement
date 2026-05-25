import sqlite3
import os

DB_PATH = "/home/ivjiyeonb/projects/financial_statement/data/financial_data.db"

def clear_database(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables_to_clear = ['financial_statements']
        
        for table in tables_to_clear:
            cursor.execute(f"DELETE FROM {table};")
            print(f"Cleared table: {table}")
        
        conn.commit()
        print("Database cleared successfully.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Ensure the directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    clear_database(DB_PATH)
