#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define project root and virtual environment paths
PROJECT_ROOT="/home/ivjiyeonb/projects/financial_statement"
VENV_DART="${PROJECT_ROOT}/venv_dart"
VENV_KRX="${PROJECT_ROOT}/venv_krx"
LOG_FILE="${PROJECT_ROOT}/scripts/run_all_process.log"

# Clear the main log file at the start of each run
> "${LOG_FILE}"

# Redirect stdout of this script to tee, and stderr of this script to tee, then both to LOG_FILE
# This ensures both stdout and stderr of the shell script itself are logged.
# Python script's internal logging.basicConfig will handle its own file.
exec > >(tee -a "${LOG_FILE}") 2>&1

# Specific error log for analyze_and_identify_undervalued.py for direct debugging
ANALYZE_ERROR_LOG="${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued_error.log"
> "${ANALYZE_ERROR_LOG}" # Clear specific error log

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

    # Determine current business year and report code
    echo "Determining current business year and report code from dart.util..."
    EVAL_PYTHON_OUTPUT=$("${VENV_DART}/bin/python3" -c "from datetime import datetime; from dart.util import determine_recent_report_code_and_year; bsns_year, reprt_code, _ = determine_recent_report_code_and_year(datetime.now()); print(f\"BSNS_YEAR={bsns_year}\"); print(f\"REPRT_CODE={reprt_code}\")")
    
    BSNS_YEAR=$(echo "${EVAL_PYTHON_OUTPUT}" | grep "BSNS_YEAR" | cut -d= -f2)
    REPRT_CODE=$(echo "${EVAL_PYTHON_OUTPUT}" | grep "REPRT_CODE" | cut -d= -f2)
    
    if [ -z "${BSNS_YEAR}" ] || [ -z "${REPRT_CODE}" ]; then
        echo "Error: Could not determine BSNS_YEAR or REPRT_CODE. Exiting." >> "${LOG_FILE}"
        exit 1
    fi

    echo "Determined BSNS_YEAR=${BSNS_YEAR}, REPRT_CODE=${REPRT_CODE}" >> "${LOG_FILE}"

    # Export for fetch_financial_data_for_filtered_companies.py
    export TARGET_BSNS_YEAR="${BSNS_YEAR}"
    export TARGET_REPRT_CODE="${REPRT_CODE}"

    # 1. Fetch KRX sector data
echo "Running krx_sector/get_krx_sector_data_final.py..."
"${VENV_KRX}/bin/python3" "${PROJECT_ROOT}/krx_sector/get_krx_sector_data_final.py"

# 2. Fetch DART financial statements
echo "Running dart/get_financial_statements.py..."
#"${VENV_DART}/bin/python3" "${PROJECT_ROOT}/dart/get_financial_statements.py"

# Clear analysis-related tables before proceeding to filtering
echo "Running scripts/clear_analysis_tables.py to clear old analysis data..."
"${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/clear_analysis_tables.py"

# 3. Analyze and identify undervalued companies (Stage 1 & 2 Filtering)
echo "Running scripts/analyze_and_identify_undervalued.py (Stage 1 & 2)..."
"${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 1_2 --bsns_year "${BSNS_YEAR}" --reprt_code "${REPRT_CODE}"

# 4. Fetch stock prices and outstanding shares for Stage 1&2 filtered companies
echo "Running scripts/fetch_financial_data_for_filtered_companies.py..."
"${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/fetch_financial_data_for_filtered_companies.py"

# 5. Analyze and identify undervalued companies (Stage 3 Filtering with PER, PBR, ROE)
PYTHON_REPORT=$("${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 3 --bsns_year "${BSNS_YEAR}" --reprt_code "${REPRT_CODE}" 2>> "${LOG_FILE}")

if [ $? -ne 0 ]; then
    echo "Error in analyze_and_identify_undervalued.py Stage 3. Check ${ANALYZE_ERROR_LOG} for details."
    cat "${ANALYZE_ERROR_LOG}"
    exit 1
else
    echo "${PYTHON_ANALYZE_REPORT}"
fi

echo "All financial analysis processes completed successfully at $(date)."
