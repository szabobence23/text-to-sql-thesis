\echo 'Importing customers...'

COPY customers
FROM '/data/olist/olist_customers_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing sellers...'

COPY sellers
FROM '/data/olist/olist_sellers_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing products...'

COPY products
FROM '/data/olist/olist_products_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing category translations...'

COPY product_category_name_translation
FROM '/data/olist/product_category_name_translation.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing orders...'

COPY orders
FROM '/data/olist/olist_orders_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing order items...'

COPY order_items
FROM '/data/olist/olist_order_items_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing payments...'

COPY order_payments
FROM '/data/olist/olist_order_payments_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing reviews...'

COPY order_reviews
FROM '/data/olist/olist_order_reviews_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Importing geolocation...'

COPY geolocation
FROM '/data/olist/olist_geolocation_dataset.csv'
WITH (
    FORMAT csv,
    HEADER true,
    NULL ''
);


\echo 'Olist import completed!';