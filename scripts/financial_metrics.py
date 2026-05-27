
import sqlite3

def calculate_per_pbr(corp_code: str, stock_code: str, bsns_year: str, db_path: str):
    """
    Calculates PER and PBR for a given company and business year.

    Args:
        corp_code (str): The corporate code.
        stock_code (str): The stock code.
        bsns_year (str): The business year.
        db_path (str): Path to the SQLite database.

    Returns:
        tuple: (per, pbr) or (None, None) if data is insufficient.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    per = None
    pbr = None

    try:
        # Fetch latest outstanding_shares
        cursor.execute(f"""
            SELECT outstanding_shares FROM outstanding_shares_data
            WHERE stock_code = '{stock_code}' AND trade_date LIKE '{bsns_year}%'
            ORDER BY trade_date DESC LIMIT 1
        """)
        outstanding_shares_result = cursor.fetchone()
        outstanding_shares = outstanding_shares_result[0] if outstanding_shares_result else None

        # Fetch latest stck_clpr (종가)
        cursor.execute(f"""
            SELECT close_price FROM stock_prices_data
            WHERE stock_code = '{stock_code}' AND trade_date LIKE '{bsns_year}%'
            ORDER BY trade_date DESC LIMIT 1
        """)
        stck_clpr_result = cursor.fetchone()
        stck_clpr = stck_clpr_result[0] if stck_clpr_result else None

        # Fetch financial statements data
        cursor.execute(f"""
            SELECT
                liquid_assets_current_liabilities,
                stock_equity,
                profit_or_loss_from_operations,
                net_profit_or_loss
            FROM financial_statements_data
            WHERE corp_code = '{corp_code}' AND bsns_year = '{bsns_year}'
        """)
        fs_data = cursor.fetchone()

        if outstanding_shares and stck_clpr and fs_data:
            liquid_assets_current_liabilities, stock_equity, profit_or_loss_from_operations, net_profit_or_loss = fs_data

            # Calculate PER
            if net_profit_or_loss and outstanding_shares:
                eps = net_profit_or_loss / outstanding_shares
                if eps > 0:
                    per = stck_clpr / eps

            # Calculate PBR
            if stock_equity and outstanding_shares:
                bps = stock_equity / outstanding_shares
                if bps > 0:
                    pbr = stck_clpr / bps

    except Exception as e:
        print(f"Error calculating PER/PBR for {corp_code} ({stock_code}, {bsns_year}): {e}")
    finally:
        conn.close()

    return per, pbr

