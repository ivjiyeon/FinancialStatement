#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define project root and virtual environment paths
PROJECT_ROOT="/home/ivjiyeonb/projects/financial_statement"
VENV_DART="${PROJECT_ROOT}/venv_dart"
VENV_KRX="${PROJECT_ROOT}/venv_krx"
LOG_FILE="${PROJECT_ROOT}/scripts/run_all_process.log"

# Clear the log file at the start of each run
> "${LOG_FILE}"

# Redirect all subsequent output to the log file
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "Starting all financial analysis processes at $(date)..."

# Load environment variables from .env file
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found at ${PROJECT_ROOT}/.env"
fi

# Set PYTHONPATH to include the project root for module imports
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# 1. Fetch KRX sector data
echo "Running krx_sector/get_krx_sector_data_final.py..."
source "${VENV_KRX}/bin/activate"
python3 "${PROJECT_ROOT}/krx_sector/get_krx_sector_data_final.py"
deactivate

# 2. Fetch DART financial statements
echo "Running dart/get_financial_statements.py..."
> "${PROJECT_ROOT}/dart/get_financial_statements.log"
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/dart/get_financial_statements.py"
deactivate

# Clear analysis-related tables before proceeding to filtering
echo "Running scripts/clear_analysis_tables.py to clear old analysis data..."
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/clear_analysis_tables.py"
deactivate

# 3. Analyze and identify undervalued companies (Stage 1 & 2 Filtering)
echo "Running scripts/analyze_and_identify_undervalued.py (Stage 1 & 2)..."
> "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.log"
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 1_2
deactivate

# 4. Fetch stock prices and outstanding shares for Stage 1&2 filtered companies
echo "Running scripts/fetch_financial_data_for_filtered_companies.py..."
> "${PROJECT_ROOT}/scripts/fetch_financial_data_for_filtered_companies.log"
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/fetch_financial_data_for_filtered_companies.py"
deactivate

# 5. Analyze and identify undervalued companies (Stage 3 Filtering with PER, PBR, ROE)
echo "Running scripts/analyze_and_identify_undervalued.py (Stage 3)..."
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 3
deactivate

echo "All financial analysis processes completed successfully at $(date)."
