#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define project root and virtual environment paths
PROJECT_ROOT="/home/ivjiyeonb/projects/financial_statement"
VENV_DART="${PROJECT_ROOT}/venv_dart"
VENV_KRX="${PROJECT_ROOT}/venv_krx"

# Load environment variables from .env file
if [ -f "${PROJECT_ROOT}/.env" ]; then
    export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found at ${PROJECT_ROOT}/.env"
fi

# Set PYTHONPATH to include the project root for module imports
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

echo "Starting all financial analysis processes..."

# 1. Fetch KRX sector data
echo "Running krx_sector/get_krx_sector_data_final.py..."
# Activate venv_krx for pykrx-related operations if get_krx_sector_data_final.py uses pykrx
# Assuming get_krx_sector_data_final.py uses pykrx
source "${VENV_KRX}/bin/activate"
python3 "${PROJECT_ROOT}/krx_sector/get_krx_sector_data_final.py"
deactivate # Deactivate venv_krx

# 2. Fetch DART financial statements
echo "Running dart/get_financial_statements.py..."
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/dart/get_financial_statements.py"
deactivate # Deactivate venv_dart

# 3. Analyze and identify undervalued companies (Stage 1 & 2 Filtering)
echo "Running scripts/analyze_and_identify_undervalued.py (Stage 1 & 2)..."
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 1_2
deactivate # Deactivate venv_dart

# 4. Fetch stock prices and outstanding shares for Stage 1&2 filtered companies
echo "Running scripts/fetch_financial_data_for_filtered_companies.py..."
# This script internally manages venv_krx and venv_dart for its subprocesses,
# so we activate venv_dart for the main script
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/fetch_financial_data_for_filtered_companies.py"
deactivate # Deactivate venv_dart

# 5. Analyze and identify undervalued companies (Stage 3 Filtering with PER, PBR, ROE)
echo "Running scripts/analyze_and_identify_undervalued.py (Stage 3)..."
source "${VENV_DART}/bin/activate"
python3 "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 3
deactivate # Deactivate venv_dart

echo "All financial analysis processes completed successfully."
