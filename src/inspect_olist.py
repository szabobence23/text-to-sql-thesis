import csv
from pathlib import Path


DATA_DIR = Path("database/olist")


for csv_file in sorted(DATA_DIR.glob("*.csv")):
    print("=" * 70)
    print(f"FILE: {csv_file.name}")

    with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)

        header = next(reader)

        row_count = 0

        for _ in reader:
            row_count += 1

    print(f"Rows: {row_count}")
    print("Columns:")

    for column in header:
        print(f"  - {column}")