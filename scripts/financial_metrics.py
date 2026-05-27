
import sqlite3
import logging

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
                fsi_profit.thstrm_amount AS net_profit_or_loss,
                fsi_equity.thstrm_amount AS stock_equity
            FROM statement_metadata AS sm
            JOIN financial_statement_items AS fsi_profit
                ON sm.corp_code = fsi_profit.corp_code
                AND sm.bsns_year = fsi_profit.bsns_year
                AND sm.reprt_code = fsi_profit.reprt_code
                AND sm.sj_div = fsi_profit.sj_div
            JOIN financial_statement_items AS fsi_equity
                ON sm.corp_code = fsi_equity.corp_code
                AND sm.bsns_year = fsi_equity.bsns_year
                AND sm.reprt_code = fsi_equity.reprt_code
                AND sm.sj_div = fsi_equity.sj_div
            WHERE
                sm.corp_code = '{corp_code}'
                AND sm.bsns_year = '{bsns_year}'
                AND fsi_profit.account_id = 'ifrs-full_ProfitLoss'
                AND fsi_profit.sj_div = 'IS'
                AND fsi_equity.account_id = 'ifrs-full_Equity'
                AND fsi_equity.sj_div = 'BS'
        """)
        fs_data = cursor.fetchone()

        logging.info(f"DEBUG {corp_code} ({stock_code}, {bsns_year}) - outstanding_shares: {outstanding_shares}, close_price: {stck_clpr}, fs_data: {fs_data}")
        if outstanding_shares and stck_clpr and fs_data:
            net_profit_or_loss, stock_equity = fs_data
            logging.info(f"DEBUG {corp_code} ({stock_code}, {bsns_year}) - net_profit_or_loss: {net_profit_or_loss}, stock_equity: {stock_equity}")
            print(f"stck_clpr: {stck_clpr}")
            # Calculate PER
            if net_profit_or_loss and outstanding_shares:
                eps = net_profit_or_loss / outstanding_shares
                print(eps)
                if eps > 0:
                    per = stck_clpr / eps

            # Calculate PBR
            if stock_equity and outstanding_shares:
                bps = stock_equity / outstanding_shares
                print(bps)
                if bps > 0:
                    pbr = stck_clpr / bps

    except Exception as e:
        print(f"Error calculating PER/PBR for {corp_code} ({stock_code}, {bsns_year}): {e}")
    finally:
        conn.close()

    return per, pbr

