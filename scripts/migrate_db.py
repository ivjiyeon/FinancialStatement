import sqlite3

DATABASE = '/home/ivjiyeonb/projects/financial_statement/data/financial_data.db'

def migrate_data():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Step 1: Populate statement_metadata table
        print("Populating statement_metadata table...")
        cursor.execute("""
            INSERT OR IGNORE INTO statement_metadata (
                rcept_no, bsns_year, corp_code, stock_code, reprt_code, sj_div, fs_div, fs_nm, currency
            )
            SELECT
                rcept_no, bsns_year, corp_code, stock_code, reprt_code, sj_div, fs_div, fs_nm, currency
            FROM
                financial_statements
            GROUP BY
                corp_code, bsns_year, reprt_code, sj_div;
        """)
        print(f"Inserted {cursor.rowcount} rows into statement_metadata.")

        # Step 2: Populate financial_statement_items table
        print("Populating financial_statement_items table...")
        cursor.execute("""
            INSERT INTO financial_statement_items (
                corp_code, bsns_year, reprt_code, sj_div, account_id, account_nm, account_detail,
                thstrm_nm, thstrm_dt, thstrm_amount, thstrm_add_amount, ord
            )
            SELECT
                corp_code, bsns_year, reprt_code, sj_div, account_id, account_nm, account_detail,
                thstrm_nm, thstrm_dt, thstrm_amount, thstrm_add_amount, ord
            FROM
                financial_statements;
        """)
        print(f"Inserted {cursor.rowcount} rows into financial_statement_items.")

        conn.commit()
        print("Data migration completed successfully.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_data()
