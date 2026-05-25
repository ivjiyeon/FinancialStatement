import sqlite3

DATABASE_PATH = '/home/ivjiyeonb/projects/financial_statement/financial_data.db'

def print_table_schema(db_path, table_name):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        print(f"\nSchema for table: {table_name}")
        for col_info in cursor.fetchall():
            print(col_info)
    except sqlite3.Error as e:
        print(f"Database error for table {table_name}: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print_table_schema(DATABASE_PATH, "balance_sheet")
    print_table_schema(DATABASE_PATH, "income_statement")
    print_table_schema(DATABASE_PATH, "cash_flow")
