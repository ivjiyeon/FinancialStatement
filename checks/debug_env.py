import sys
import os

print("Current working directory:", os.getcwd())
print("sys.prefix:", sys.prefix)
print("sys.base_prefix:", sys.base_prefix)
print("sys.path:")
for p in sys.path:
    print(f"  - {p}")

print("\nAttempting to import 'opendartreader' (lowercase):")
try:
    import opendartreader
    print("opendartreader (lowercase) imported successfully.")
except ImportError as e:
    print(f"Failed to import opendartreader (lowercase): {e}")

print("\nAttempting to import 'OpenDartReader' (capitalized):")
try:
    import OpenDartReader
    print("OpenDartReader (capitalized) imported successfully.")
except ImportError as e:
    print(f"Failed to import OpenDartReader (capitalized): {e}")

try:
    import FinanceDataReader as fdr
    print("FinanceDataReader imported successfully.")
except ImportError as e:
    print(f"Failed to import FinanceDataReader: {e}")