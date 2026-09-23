import csv
from pathlib import Path


DATA_DIR = Path("database/olist")


def load_column(filename, column):
    """
    Beolvassa egy CSV adott oszlopát egy set-be.
    A set miatt nagyon gyorsan tudunk később
    membershipet ellenőrizni.
    """

    path = DATA_DIR / filename

    values = set()

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:
            value = row[column]

            if value is not None and value.strip() != "":
                values.add(value.strip())

    return values


def validate_relationship(
    child_file,
    child_column,
    parent_file,
    parent_column,
    child_values,
    parent_values
):
    """
    Ellenőrzi, hogy a child táblában szereplő
    foreign key értékek mind megtalálhatók-e
    a parent táblában.
    """

    invalid_values = child_values - parent_values

    print("=" * 80)

    print(
        f"{child_file}.{child_column}"
        f" -> "
        f"{parent_file}.{parent_column}"
    )

    print(f"Child unique values:  {len(child_values):,}")
    print(f"Parent unique values: {len(parent_values):,}")
    print(f"Invalid references:    {len(invalid_values):,}")

    if invalid_values:
        print("\nERROR: Invalid references found!")

        # Maximum 10 példát írunk ki
        print("Examples:")

        for value in list(invalid_values)[:10]:
            print(f"  {value}")

        return False

    print("OK: All references are valid.")

    return True


# ============================================================
# 1. Adatok betöltése
# ============================================================

print("Loading CSV columns...\n")


customers = load_column(
    "olist_customers_dataset.csv",
    "customer_id"
)

orders = load_column(
    "olist_orders_dataset.csv",
    "order_id"
)

order_customer_ids = load_column(
    "olist_orders_dataset.csv",
    "customer_id"
)

order_items_order_ids = load_column(
    "olist_order_items_dataset.csv",
    "order_id"
)

order_items_product_ids = load_column(
    "olist_order_items_dataset.csv",
    "product_id"
)

order_items_seller_ids = load_column(
    "olist_order_items_dataset.csv",
    "seller_id"
)

products = load_column(
    "olist_products_dataset.csv",
    "product_id"
)

sellers = load_column(
    "olist_sellers_dataset.csv",
    "seller_id"
)

payment_order_ids = load_column(
    "olist_order_payments_dataset.csv",
    "order_id"
)

review_order_ids = load_column(
    "olist_order_reviews_dataset.csv",
    "order_id"
)


print("CSV data loaded.\n")


# ============================================================
# 2. Kapcsolatok validálása
# ============================================================

results = []


# orders.customer_id -> customers.customer_id

results.append(
    validate_relationship(
        "orders",
        "customer_id",
        "customers",
        "customer_id",
        order_customer_ids,
        customers
    )
)


# order_items.order_id -> orders.order_id

results.append(
    validate_relationship(
        "order_items",
        "order_id",
        "orders",
        "order_id",
        order_items_order_ids,
        orders
    )
)


# order_items.product_id -> products.product_id

results.append(
    validate_relationship(
        "order_items",
        "product_id",
        "products",
        "product_id",
        order_items_product_ids,
        products
    )
)


# order_items.seller_id -> sellers.seller_id

results.append(
    validate_relationship(
        "order_items",
        "seller_id",
        "sellers",
        "seller_id",
        order_items_seller_ids,
        sellers
    )
)


# order_payments.order_id -> orders.order_id

results.append(
    validate_relationship(
        "order_payments",
        "order_id",
        "orders",
        "order_id",
        payment_order_ids,
        orders
    )
)


# order_reviews.order_id -> orders.order_id

results.append(
    validate_relationship(
        "order_reviews",
        "order_id",
        "orders",
        "order_id",
        review_order_ids,
        orders
    )
)


# ============================================================
# 3. Összesítés
# ============================================================

print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

passed = sum(results)
total = len(results)

print(f"Passed: {passed}/{total}")
print(f"Failed: {total - passed}/{total}")

if passed == total:
    print("\nSUCCESS: All planned foreign key relationships are valid.")
else:
    print("\nWARNING: Some foreign key relationships contain invalid references.")