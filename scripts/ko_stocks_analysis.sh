#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define project root and virtual environment paths
PROJECT_ROOT="/home/ivjiyeonb/projects/financial_statement"
VENV_DART="${PROJECT_ROOT}/venv_dart"
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
        # Read .env file line by line and export variables
        while IFS='=' read -r key value; do
            if [[ ! -z "$key" && ! "$key" =~ ^# ]]; then
                export "$key"="$value"
            fi
        done < "${PROJECT_ROOT}/.env"
        echo "Environment variables loaded from .env"
    else
        echo "Warning: .env file not found at ${PROJECT_ROOT}/.env"
    fi





    # 1. Fetch KRX sector data (if uncommented in the future)
    # echo "Running krx_sector/get_krx_sector_data_final.py..."
    # "${VENV_KRX}/bin/python3" "${PROJECT_ROOT}/krx_sector/get_krx_sector_data_final.py"

    # 2. Fetch DART financial statements (if uncommented in the future)
    # echo "Running dart/get_financial_statements.py..."
    # "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/dart/get_financial_statements.py"

    # Clear analysis-related tables before proceeding to filtering
    echo "Running scripts/clear_analysis_tables.py to clear old analysis data..."
    "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/clear_analysis_tables.py"

    echo "Running scripts/analyze_and_identify_undervalued.py (Full Analysis)..."
    # Execute the main analysis script. Its stdout is captured later for reporting.
    # Its stderr is redirected to ANALYZE_ERROR_LOG.
    "${VENV_DART}/bin/python3" "${PROJECT_ROOT}/scripts/analyze_and_identify_undervalued.py" 2> >(tee -a "${ANALYZE_ERROR_LOG}" >&2)

    echo "All financial analysis processes completed successfully at $(date)..."

) >> "${LOG_FILE}" 2>&1

# Capture the output of the main analysis script from the log file for Discord delivery.
# This assumes analyze_and_identify_undervalued.py prints its report to stdout,
# which is redirected to LOG_FILE.
# We need to extract only the report section, which starts with "Healthy Companies:" or "Undervalued Companies:" or "No companies detected".
REPORT_START_KEYWORD="Healthy Companies:"
REPORT_START_KEYWORD2="Undervalued Companies:"
REPORT_START_KEYWORD3="No companies detected"
REPORT_CONTENT=$(grep -A 10000 -E "${REPORT_START_KEYWORD}|${REPORT_START_KEYWORD2}|${REPORT_START_KEYWORD3}" "${LOG_FILE}" || true) # Use || true to prevent pipefail if grep finds nothing

if [ -z "${REPORT_CONTENT}" ]; then
    # If no report content is found, it means the Python script either failed silently or produced no output.
    # In this case, we check the ANALYZE_ERROR_LOG for errors.
    if [ -s "${ANALYZE_ERROR_LOG}" ]; then # -s checks if file exists and has size greater than zero
        echo "Error: Financial analysis script produced no report. Check ${ANALYZE_ERROR_LOG} for errors."
        echo "MEDIA:${ANALYZE_ERROR_LOG}"
    else
        echo "Error: Financial analysis script produced no output and no errors were logged."
    fi
else
    # Output the report content to standard output for cron job delivery
    echo "${REPORT_CONTENT}"
fi
