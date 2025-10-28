import pandas as pd
import json

# Read the Excel file
excel_path = r'c:\LAB DATA ANALYZER\GEMINI 2.0\DIAGNOSTIC TOOL\Calculations-DDT.xlsx'
xls = pd.ExcelFile(excel_path)

print("=" * 80)
print("EXCEL FILE STRUCTURE ANALYSIS")
print("=" * 80)

# Get sheet names
print(f"\nSheet names: {xls.sheet_names}")

# Read the first sheet
df = pd.read_excel(xls, sheet_name=0)

print(f"\nDataFrame Shape: {df.shape[0]} rows x {df.shape[1]} columns")
print("\n" + "=" * 80)
print("COLUMN NAMES (In Order)")
print("=" * 80)

for i, col in enumerate(df.columns, 1):
    print(f"{i:3d}. {col}")

print("\n" + "=" * 80)
print("FIRST 5 ROWS OF DATA")
print("=" * 80)
print(df.head(5).to_string())

print("\n" + "=" * 80)
print("DATA TYPES")
print("=" * 80)
print(df.dtypes)

print("\n" + "=" * 80)
print("SAMPLE VALUES FOR EACH COLUMN (First Row)")
print("=" * 80)
if len(df) > 0:
    for col in df.columns:
        value = df[col].iloc[0]
        print(f"{col:40s} : {value}")

# Save column structure to JSON
column_structure = {
    'sheet_names': xls.sheet_names,
    'columns': list(df.columns),
    'shape': df.shape,
    'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()}
}

with open('excel_structure.json', 'w') as f:
    json.dump(column_structure, f, indent=2)

print("\n" + "=" * 80)
print("Column structure saved to excel_structure.json")
print("=" * 80)
