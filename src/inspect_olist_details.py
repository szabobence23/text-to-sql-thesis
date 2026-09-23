import csv
from pathlib import Path


DATA_DIR = Path("database/olist")


# Azok az oszlopok, amelyeket kulcsként szeretnénk megvizsgálni
KEY_COLUMNS = {
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id"],
    "olist_orders_dataset.csv": ["order_id", "customer_id"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id", "product_id", "seller_id"],
    "olist_products_dataset.csv": ["product_id"],
    "olist_sellers_dataset.csv": ["seller_id"],
    "olist_order_payments_dataset.csv": ["order_id"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix"],
    "product_category_name_translation.csv": [
        "product_category_name",
        "product_category_name_english"
    ],
}


for csv_file in sorted(DATA_DIR.glob("*.csv")):

    print("=" * 80)
    print(f"FILE: {csv_file.name}")

    # --------------------------------------------------
    # Első passz: sorok, NULL-ok, kulcsok
    # --------------------------------------------------

    with open(
        csv_file,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        columns = reader.fieldnames

        null_counts = {
            column: 0
            for column in columns
        }

        row_count = 0

        key_values = {
            column: set()
            for column in KEY_COLUMNS.get(csv_file.name, [])
        }

        duplicate_counts = {
            column: 0
            for column in key_values
        }

        for row in reader:

            row_count += 1

            for column in columns:

                value = row[column]

                if value is None or value.strip() == "":
                    null_counts[column] += 1

            for column in key_values:

                value = row[column]

                if value is None or value.strip() == "":
                    continue

                if value in key_values[column]:
                    duplicate_counts[column] += 1
                else:
                    key_values[column].add(value)

    print(f"\nRows: {row_count}")

    print("\nNULL values:")

    for column, count in null_counts.items():

        if count > 0:
            percentage = count / row_count * 100

            print(
                f"  {column}: "
                f"{count} ({percentage:.2f}%)"
            )

    print("\nKey candidates:")

    for column in key_values:

        unique_count = len(key_values[column])
        duplicate_count = duplicate_counts[column]

        print(
            f"  {column}: "
            f"{unique_count} unique, "
            f"{duplicate_count} duplicate rows"
        )

    # --------------------------------------------------
    # Első 3 sor
    # --------------------------------------------------

    print("\nSample rows:")

    with open(
        csv_file,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for i, row in enumerate(reader):

            print(f"  Row {i + 1}: {row}")

            if i >= 2:
                break