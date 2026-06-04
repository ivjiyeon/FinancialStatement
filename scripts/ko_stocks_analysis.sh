#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define project root and virtual environment paths
PROJECT_ROOT="/home/ivjiyeonb/projects/financial_statement"
VENV_DART="${PROJECT_ROOT}/venv_dart"
VENV_KRX="${PROJECT_ROOT}/venv_krx"
LOG_FILE="${PROJECT_ROOT}/scripts/run_all_process.log"
ANALYZE_ERROR_LOG="${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued_error.log"

# Set PYTHONPATH to include the project root for module imports
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Clear log files at the start of each run
> "${LOG_FILE}"
> "${ANALYZE_ERROR_LOG}"

# Determine current business year and report code
EVAL_PYTHON_OUTPUT=$("${VENV_DART}/bin/python3" -c "from datetime import datetime; from dart.util import determine_recent_report_code_and_year; bsns_year, reprt_code, _ = determine_recent_report_code_and_year(datetime.now()); print(f\"BSNS_YEAR={bsns_year}\"); print(f\"REPRT_CODE={reprt_code}\")")

BSNS_YEAR=$(echo "${EVAL_PYTHON_OUTPUT}" | grep "BSNS_YEAR" | cut -d= -f2)
REPRT_CODE=$(echo "${EVAL_PYTHON_OUTPUT}" | grep "REPRT_CODE" | cut -d= -f2)

if [ -z "${BSNS_YEAR}" ] || [ -z "${REPRT_CODE}" ]; then
    echo "Error: Could not determine BSNS_YEAR or REPRT_CODE. Exiting."
    exit 1
fi



# Export for Python scripts
export TARGET_BSNS_YEAR="${BSNS_YEAR}"
export TARGET_REPRT_CODE="${REPRT_CODE}"

# All intermediate output goes to LOG_FILE
(
    echo "Starting all financial analysis processes at $(date)..."

    # Load environment variables from .env file
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        export $(grep -v '^#' "${PROJECT_ROOT}/.env" | xargs)
        echo "Environment variables loaded from .env"
    else
        echo "Warning: .env file not found at ${PROJECT_ROOT}/.env"
    fi







    # 1. Fetch KRX sector data
    echo "Running krx_sector/get_krx_sector_data_final.py..."
    # "${VENV_KRX}/bin/python3" "${PROJECT_ROOT}/krx_sector/get_krx_sector_data_final.py"

    # 2. Fetch DART financial statements
    echo "Running dart/get_financial_statements.py..."
    # "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/dart/get_financial_statements.py"

    # Clear analysis-related tables before proceeding to filtering
    echo "Running scripts/clear_analysis_tables.py to clear old analysis data..."
    "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/clear_analysis_tables.py"

    # 3. Analyze and identify undervalued companies (Stage 1 & 2 Filtering)
    echo "Running scripts/analyze_and_identify_undervalued.py (Stage 1 & 2)..."
    "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 1_2



    echo "All financial analysis processes completed successfully at $(date)..."

) >> "${LOG_FILE}" 2>&1

# 5. Analyze and identify undervalued companies (Stage 3 Filtering with PER, PBR, ROE)
# The stdout of this script is captured into PYTHON_REPORT
# The stderr of this script is redirected to ANALYZE_ERROR_LOG
PYTHON_REPORT=$("${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" --stage 3 2>> "${ANALYZE_ERROR_LOG}")

if [ $? -ne 0 ]; then
    # If the Python script failed, output a generic error message
    echo "Error: Financial analysis failed in Stage 3. Check ${ANALYZE_ERROR_LOG} for details in the attached log."
    # Attach the log file for debugging
    echo "MEDIA:${ANALYZE_ERROR_LOG}"
    exit 1
else
    # Finally, echo only the PYTHON_REPORT to standard output for cron job delivery
    echo "${PYTHON_REPORT}"
fi
