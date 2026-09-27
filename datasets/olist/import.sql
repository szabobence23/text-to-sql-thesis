\echo 'Importing customers...'

COPY customers
FROM '/datasets/olist/data/olist_customers_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing sellers...'

COPY sellers
FROM '/datasets/olist/data/olist_sellers_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing products...'

COPY products
FROM '/datasets/olist/data/olist_products_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing category translations...'

COPY product_category_name_translation
FROM '/datasets/olist/data/product_category_name_translation.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing orders...'

COPY orders
FROM '/datasets/olist/data/olist_orders_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing order items...'

COPY order_items
FROM '/datasets/olist/data/olist_order_items_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing payments...'

COPY order_payments
FROM '/datasets/olist/data/olist_order_payments_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing reviews...'

COPY order_reviews
FROM '/datasets/olist/data/olist_order_reviews_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing geolocation...'

COPY geolocation
FROM '/datasets/olist/data/olist_geolocation_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Olist import completed!';