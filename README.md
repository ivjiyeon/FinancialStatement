# FinancialStatement

This project provides a comprehensive solution for automated financial statement analysis, focusing on data acquisition from Korea's DART (Data Analysis, Retrieval and Transfer) and KRX (Korea Exchange) systems to identify undervalued companies.

## Features

-   **DART Data Acquisition**: Scripts to fetch and process financial statements from the DART API, including historical data and company information.
-   **KRX Sector Data Acquisition**: Tools to acquire and manage sector-specific data from the Korea Exchange.
-   **Financial Data Storage**: Utilizes a SQLite database to store collected financial and company information efficiently.
-   **Undervalued Company Analysis**: Scripts to analyze financial data based on predefined criteria to identify potentially undervalued stocks.
-   **Virtual Environment Management**: Dedicated virtual environments for DART and KRX related scripts to manage dependencies.

## Project Structure

-   `dart/`: Contains scripts for DART API interaction, including data fetching, processing, and database operations.
-   `krx_sector/`: Houses scripts for acquiring and processing KRX sector data.
-   `data/`: Stores various datasets, including CSV files for Balance Sheets (bs.csv), Cash Flows (cf.csv), Income Statements (is.csv), and KRX sector data (krx_sector_data.csv). The `financial_data.db` SQLite database is also located here.
-   `checks/`: Utility scripts for checking data integrity and database schema.
-   `scripts/`: Contains general-purpose scripts, including analysis tools.
-   `venv_dart/`: Python virtual environment for DART-related dependencies.
-   `venv_krx/`: Python virtual environment for KRX-related dependencies.
-   `README.md`: This project overview.
-   `.gitignore`: Specifies files and directories to be ignored by Git, such as virtual environments and the large `financial_data.db`.
-   `file_details.md`: Detailed descriptions of each file and directory within the project.
-   `undervalued_standard.md`: Documentation outlining the criteria used for identifying undervalued companies.

## Setup and Installation

*(Placeholder for future instructions on setting up the project, installing dependencies, and running the scripts.)*

## Usage

*(Placeholder for future instructions on how to use the various scripts and functionalities.)*

## Contributing

*(Placeholder for future guidelines on how others can contribute to the project.)*

## License

*(Placeholder for project license information.)*
