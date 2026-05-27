# File Details

This document provides a concise description of the purpose of each file and directory within the `~/projects/financial_statement/` project.

## Root Directory (`~/projects/financial_statement/`)

- `README.md`: Main project description and overview.
- `.gitignore`: Specifies intentionally untracked files to ignore.
- `checklist.md`: Project checklist or task tracker for managing project progress.
- `debug_env.py`: Script likely used for debugging environment configurations or settings.
- `file_details.md`: This document, providing descriptions of all project files.
- `undervalued_standard.md`: Markdown document outlining the criteria or standards used to identify undervalued stocks.

## `dart/` Directory (DART API Interaction)

This directory contains scripts related to fetching and processing financial data from the DART (Data Analysis, Retrieval and Transfer) API.

- `analyze_and_identify_undervalued.py`: Python script for analyzing financial data from DART to identify undervalued companies based on predefined criteria.
- `check_dart_methods.py`: Utility script to test or verify the functionality of various DART API interaction methods.
- `check_fdr_columns.py`: Script to ensure consistency and correctness of columns, potentially from FinanceDataReader.
- `fetch_initial_data.py`: A new script specifically designed to extract one year of historical financial statement data for all companies, now inserting into the `statement_metadata` and `financial_statement_items` tables.
- `get_db_schema.py`: Script for defining or retrieving the database schema used for financial data storage.
- `get_financial_statements.log`: Log file recording the execution and activities of the `get_financial_statements.py` script.
- `get_financial_statements.py`: The primary script responsible for fetching the *latest* financial statements from the DART API. It now uses common utility functions from `dart/util.py` and includes logic to remove financial data older than 1.5 years.
- `populate_company_info.py`: Script to populate or update company information, such as corporate codes, in the project database.
- `store_financial_data_to_db.py`: Script dedicated to inserting or updating processed financial statement data into the SQLite database.
- `util.py`: A utility file containing common functions shared by DART-related scripts (e.g., XML/JSON parsing, database connection, data insertion into new `statement_metadata` and `financial_statement_items` tables, data cleaning, etc.).

## `data/` Directory (Data Storage)

This directory is used for storing various datasets, including financial statements and KRX sector data.

- `bs.csv`: CSV file likely containing Balance Sheet data.
- `cf.csv`: CSV file likely containing Cash Flow data.
- `financial_data.db`: The SQLite database storing all collected financial and company information, now containing `statement_metadata` and `financial_statement_items` tables.
- `is.csv`: CSV file likely containing Income Statement data.
- `krx_sector_data.csv`: CSV file storing sector-specific data acquired from the Korea Exchange (KRX).
- `statement_metadata`: Table storing metadata for financial statements (e.g., company, year, report code, financial statement type).
- `financial_statement_items`: Table storing detailed account items for financial statements.

## `krx_sector/` Directory (KRX Sector Data Acquisition)

This directory houses scripts focused on acquiring and processing sector-specific data from the Korea Exchange (KRX).

- `CORPCODE.xml`: XML file containing corporate codes, often used for mapping or cross-referencing with DART data.
- `analyze_undervalued_companies.log`: Log file generated during the analysis of undervalued companies using KRX sector data.
- `get_krx_sector_data.py`: Script for fetching general KRX sector data.
- `get_krx_sector_data_final.py`: A possibly refined or final version of the script used to acquire KRX sector data.
- `get_krx_sector_pykrx.py`: Script that utilizes the `pykrx` Python library for more efficient or specialized KRX data acquisition.
- `requirements.txt`: Lists Python package dependencies specifically for the `krx_sector` module.
- `scrape_krx_sector.py`: Script designed for web scraping KRX sector-related information.

## `scripts/` Directory (Utility Scripts)

This directory contains general utility scripts for the project.

- `analyze_and_identify_undervalued.log`: Log file for the financial analysis script.
- `analyze_and_identify_undervalued.py`: Python script for analyzing financial data.
- `financial_metrics.py`: Module containing functions for calculating financial metrics like PER and PBR.
- `fetch_financial_data_for_filtered_companies.py`: Python script to fetch stock prices and outstanding shares for companies identified as undervalued in `analyze_and_identify_undervalued.py`, storing data in new, dedicated database tables.
- `krx_data_fetch_worker.py`: Helper script executed within `venv_krx` to fetch stock prices and outstanding shares using `pykrx`.
- `migrate_db.py`: Script used for migrating data from the old `financial_statements` table to the new `statement_metadata` and `financial_statement_items` tables.

## Virtual Environment Directories

- `venv_dart/`: Python virtual environment for DART-related scripts, ensuring isolated dependencies.
- `venv_krx/`: Python virtual environment for KRX-related scripts, managing specific package versions.
