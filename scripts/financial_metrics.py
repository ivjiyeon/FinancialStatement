
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
    eps = None
    bps = None

    try:
        # Fetch latest outstanding_shares
        cursor.execute(f"""
            SELECT outstanding_shares FROM outstanding_shares_data
            WHERE stock_code = ?
            ORDER BY trade_date DESC LIMIT 1
        """, (stock_code,))
        outstanding_shares_result = cursor.fetchone()
        outstanding_shares = outstanding_shares_result[0] if outstanding_shares_result else None

        # Fetch latest close_price
        cursor.execute("""
            SELECT close_price FROM stock_prices_data
            WHERE stock_code = ?
            ORDER BY trade_date DESC LIMIT 1
        """, (stock_code,))
        close_price_result = cursor.fetchone()
        close_price = close_price_result[0] if close_price_result else None

        # Fetch financial statements data
        net_profit_or_loss = None
        profit_reprt_code = None
        thstrm_add_amount_profit = None

        # Try 'IS' first for ifrs-full_ProfitLoss
        cursor.execute(f"""
            SELECT
                thstrm_amount,
                reprt_code,
                thstrm_add_amount
            FROM financial_statement_items
            WHERE
                corp_code = ?
                AND bsns_year = ?
                AND account_id = 'ifrs-full_ProfitLoss'
                AND sj_div = ?
        """, (corp_code, bsns_year, 'IS'))
        profit_data = cursor.fetchone()

        if profit_data:
            net_profit_or_loss, profit_reprt_code, additional_profit_amount = profit_data
        else:
            cursor.execute("""
                SELECT
                    thstrm_amount,
                    reprt_code,
                    thstrm_add_amount
                FROM financial_statement_items
                WHERE
                    corp_code = ?
                    AND bsns_year = ?
                    AND account_id = 'ifrs-full_ProfitLoss'
                    AND sj_div = ?
            """, (corp_code, bsns_year, 'CIS'))
            profit_data = cursor.fetchone()
            if profit_data:
                net_profit_or_loss, profit_reprt_code, additional_profit_amount = profit_data

        # Fetch stock equity
        stock_equity = None
        cursor.execute("""
            SELECT
                thstrm_amount
            FROM financial_statement_items
            WHERE
                corp_code = ?
                AND bsns_year = ?
                AND account_id = 'ifrs-full_Equity'
                AND sj_div = 'BS'
        """, (corp_code, bsns_year))
        stock_equity_data = cursor.fetchone()
        if stock_equity_data:
            stock_equity = stock_equity_data[0]

        # Apply adjustment for annual report (11011) if net_profit_or_loss was fetched with reprt_code '11011'
        ANNUAL_REPORT_CODE = '11011'
        Q3_REPORT_CODE = '11014'

        if net_profit_or_loss is not None and profit_reprt_code == ANNUAL_REPORT_CODE:
            cursor.execute("""
                SELECT
                    thstrm_add_amount
                FROM financial_statement_items
                WHERE
                    corp_code = ?
                    AND bsns_year = ?
                    AND reprt_code = ?
                    AND account_id = 'ifrs-full_ProfitLoss'
                    AND (sj_div = 'IS' OR sj_div = 'CIS')
            """, (corp_code, bsns_year, Q3_REPORT_CODE))
            q3_add_amount_result = cursor.fetchone()
            if q3_add_amount_result and q3_add_amount_result[0] is not None:
                q3_add_amount = q3_add_amount_result[0]
                net_profit_or_loss -= q3_add_amount
            else:
                logging.warning(f"Could not find Q3 (11014) thstrm_add_amount for corp_code={corp_code}, bsns_year={bsns_year} to adjust annual profit.")

        if outstanding_shares and close_price and net_profit_or_loss is not None and stock_equity is not None:
            # Calculate PER
            if net_profit_or_loss and outstanding_shares:
                eps = net_profit_or_loss / outstanding_shares * 4
                if eps > 0:
                    per = close_price / eps

            # Calculate PBR
            if stock_equity and outstanding_shares:
                bps = stock_equity / outstanding_shares
                if bps > 0:
                    pbr = close_price / bps

    except Exception as e:
        logging.error(f"Error calculating PER/PBR for {corp_code} ({stock_code}, {bsns_year}): {e}")
    finally:
        conn.close()

    return per, pbr, eps, bps

