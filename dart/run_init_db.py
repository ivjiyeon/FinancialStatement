import os
from util import init_db

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, '..')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(DATA_DIR, 'financial_data.db')

print(f"Initializing database at: {DB_PATH}")
init_db(DB_PATH)
print("Database initialization complete.")