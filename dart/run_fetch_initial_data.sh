#!/bin/bash

source /home/ivjiyeonb/projects/financial_statement/venv_dart/bin/activate
export PYTHONPATH="/home/ivjiyeonb/projects/financial_statement/:$PYTHONPATH"
/home/ivjiyeonb/projects/financial_statement/venv_dart/bin/python3 /home/ivjiyeonb/projects/financial_statement/dart/fetch_initial_data.py
deactivate
