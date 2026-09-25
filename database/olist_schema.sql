-- ============================================================
-- OLIST DATABASE SCHEMA
-- ============================================================


-- ============================================================
-- CUSTOMERS
-- ============================================================

CREATE TABLE customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    customer_unique_id VARCHAR(32) NOT NULL,
    customer_zip_code_prefix VARCHAR(5) NOT NULL,
    customer_city VARCHAR(100) NOT NULL,
    customer_state VARCHAR(2) NOT NULL
);


-- ============================================================
-- SELLERS
-- ============================================================

CREATE TABLE sellers (
    seller_id VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(5) NOT NULL,
    seller_city VARCHAR(100) NOT NULL,
    seller_state VARCHAR(2) NOT NULL
);


-- ============================================================
-- PRODUCTS
-- ============================================================

CREATE TABLE products (
    product_id VARCHAR(32) PRIMARY KEY,
    product_category_name VARCHAR(100),

    product_name_lenght INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty INTEGER,

    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);


-- ============================================================
-- CATEGORY TRANSLATION
-- ============================================================

CREATE TABLE product_category_name_translation (
    product_category_name VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100) NOT NULL
);


-- ============================================================
-- ORDERS
-- ============================================================

CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,

    customer_id VARCHAR(32) NOT NULL,

    order_status VARCHAR(20) NOT NULL,

    order_purchase_timestamp TIMESTAMP NOT NULL,
    order_approved_at TIMESTAMP,

    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,

    order_estimated_delivery_date TIMESTAMP,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id)
);


-- ============================================================
-- ORDER ITEMS
-- ============================================================

CREATE TABLE order_items (
    order_id VARCHAR(32) NOT NULL,
    order_item_id INTEGER NOT NULL,

    product_id VARCHAR(32) NOT NULL,
    seller_id VARCHAR(32) NOT NULL,

    shipping_limit_date TIMESTAMP NOT NULL,

    price DECIMAL(10, 2) NOT NULL,
    freight_value DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (order_id, order_item_id),

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id),

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products(product_id),

    CONSTRAINT fk_order_items_seller
        FOREIGN KEY (seller_id)
        REFERENCES sellers(seller_id)
);


-- ============================================================
-- ORDER PAYMENTS
-- ============================================================

CREATE TABLE order_payments (
    order_id VARCHAR(32) NOT NULL,
    payment_sequential INTEGER NOT NULL,

    payment_type VARCHAR(30) NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (order_id, payment_sequential),

    CONSTRAINT fk_order_payments_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);


-- ============================================================
-- ORDER REVIEWS
-- ============================================================

CREATE TABLE order_reviews (
    review_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) NOT NULL,

    review_score INTEGER NOT NULL,

    review_comment_title VARCHAR(255),
    review_comment_message TEXT,

    review_creation_date TIMESTAMP,
    review_answer_timestamp TIMESTAMP,

    CONSTRAINT fk_order_reviews_order
        FOREIGN KEY (order_id)
        REFERENCES orders(order_id)
);


-- ============================================================
-- GEOLOCATION
-- ============================================================

CREATE TABLE geolocation (
    geolocation_zip_code_prefix VARCHAR(5) NOT NULL,

    geolocation_lat DECIMAL(10, 8) NOT NULL,
    geolocation_lng DECIMAL(11, 8) NOT NULL,

    geolocation_city VARCHAR(100) NOT NULL,
    geolocation_state VARCHAR(2) NOT NULL
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_orders_customer_id
    ON orders(customer_id);

CREATE INDEX idx_order_items_product_id
    ON order_items(product_id);

CREATE INDEX idx_order_items_seller_id
    ON order_items(seller_id);

CREATE INDEX idx_order_payments_order_id
    ON order_payments(order_id);

CREATE INDEX idx_order_reviews_order_id
    ON order_reviews(order_id);

CREATE INDEX idx_products_category
    ON products(product_category_name);

CREATE INDEX idx_geolocation_zip
    ON geolocation(geolocation_zip_code_prefix);