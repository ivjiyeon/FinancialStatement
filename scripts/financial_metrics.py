
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
            WHERE stock_code = '{stock_code}'
            ORDER BY trade_date DESC LIMIT 1
        """)
        outstanding_shares_result = cursor.fetchone()
        outstanding_shares = outstanding_shares_result[0] if outstanding_shares_result else None

        # Fetch latest stck_clpr (종가)
        cursor.execute(f"""
            SELECT close_price FROM stock_prices_data
            WHERE stock_code = '{stock_code}'
            ORDER BY trade_date DESC LIMIT 1
        """)
        stck_clpr_result = cursor.fetchone()
        stck_clpr = stck_clpr_result[0] if stck_clpr_result else None

        # Fetch financial statements data
        net_profit_or_loss = None
        profit_reprt_code = None
        thstrm_add_amount_profit = None

        # Try 'IS' first for ifrs-full_ProfitLoss
        cursor.execute(f"""
            SELECT
                fsi_profit.thstrm_amount,
                sm.reprt_code,
                fsi_profit.thstrm_add_amount
            FROM statement_metadata AS sm
            JOIN financial_statement_items AS fsi_profit
                ON sm.corp_code = fsi_profit.corp_code
                AND sm.bsns_year = fsi_profit.bsns_year
                AND sm.reprt_code = fsi_profit.reprt_code
            WHERE
                sm.corp_code = '{corp_code}'
                AND sm.bsns_year = '{bsns_year}'
                AND fsi_profit.account_id = 'ifrs-full_ProfitLoss'
                AND fsi_profit.sj_div = 'IS'
        """)
        profit_data_is = cursor.fetchone()

        if profit_data_is:
            net_profit_or_loss, profit_reprt_code, thstrm_add_amount_profit = profit_data_is
        else:
            # If not found in 'IS', try 'CIS'
            cursor.execute(f"""
                SELECT
                    fsi_profit.thstrm_amount,
                    sm.reprt_code,
                    fsi_profit.thstrm_add_amount
                FROM statement_metadata AS sm
                JOIN financial_statement_items AS fsi_profit
                    ON sm.corp_code = fsi_profit.corp_code
                    AND sm.bsns_year = fsi_profit.bsns_year
                    AND sm.reprt_code = fsi_profit.reprt_code
                WHERE
                    sm.corp_code = '{corp_code}'
                    AND sm.bsns_year = '{bsns_year}'
                    AND fsi_profit.account_id = 'ifrs-full_ProfitLoss'
                    AND fsi_profit.sj_div = 'CIS'
            """)
            profit_data_cis = cursor.fetchone()
            if profit_data_cis:
                net_profit_or_loss, profit_reprt_code, thstrm_add_amount_profit = profit_data_cis

        # Fetch stock equity
        stock_equity = None
        cursor.execute(f"""
            SELECT
                fsi_equity.thstrm_amount
            FROM statement_metadata AS sm
            JOIN financial_statement_items AS fsi_equity
                ON sm.corp_code = fsi_equity.corp_code
                AND sm.bsns_year = fsi_equity.bsns_year
                AND sm.reprt_code = fsi_equity.reprt_code
            WHERE
                sm.corp_code = '{corp_code}'
                AND sm.bsns_year = '{bsns_year}'
                AND fsi_equity.account_id = 'ifrs-full_Equity'
                AND fsi_equity.sj_div = 'BS'
        """)
        stock_equity_data = cursor.fetchone()
        if stock_equity_data:
            stock_equity = stock_equity_data[0]

        # Apply adjustment for annual report (11011) if net_profit_or_loss was fetched with reprt_code '11011'
        if net_profit_or_loss is not None and profit_reprt_code == '11011':
            logging.info(f"Applying 11014 adjustment for corp_code={corp_code}, bsns_year={bsns_year}, original net_profit_or_loss={net_profit_or_loss}")
            cursor.execute(f"""
                SELECT
                    fsi_profit_q3.thstrm_add_amount
                FROM statement_metadata AS sm_q3
                JOIN financial_statement_items AS fsi_profit_q3
                    ON sm_q3.corp_code = fsi_profit_q3.corp_code
                    AND sm_q3.bsns_year = fsi_profit_q3.bsns_year
                    AND sm_q3.reprt_code = fsi_profit_q3.reprt_code
                WHERE
                    sm_q3.corp_code = '{corp_code}'
                    AND sm_q3.bsns_year = '{bsns_year}'
                    AND sm_q3.reprt_code = '11014'  -- Q3 report
                    AND fsi_profit_q3.account_id = 'ifrs-full_ProfitLoss'
                    AND (fsi_profit_q3.sj_div = 'IS' OR fsi_profit_q3.sj_div = 'CIS')
            """)
            q3_add_amount_result = cursor.fetchone()
            if q3_add_amount_result and q3_add_amount_result[0] is not None:
                q3_add_amount = q3_add_amount_result[0]
                net_profit_or_loss -= q3_add_amount
                logging.info(f"Subtracted Q3 thstrm_add_amount ({q3_add_amount}). Adjusted net_profit_or_loss={net_profit_or_loss}")
            else:
                logging.warning(f"Could not find Q3 (11014) thstrm_add_amount for corp_code={corp_code}, bsns_year={bsns_year} to adjust annual profit.")

        logging.info(f"DEBUG {corp_code} ({stock_code}, {bsns_year}) - outstanding_shares: {outstanding_shares}, close_price: {stck_clpr}, net_profit_or_loss: {net_profit_or_loss}, stock_equity: {stock_equity}")
        if outstanding_shares and stck_clpr and net_profit_or_loss is not None and stock_equity is not None:
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

