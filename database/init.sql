CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id),

    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
);


INSERT INTO customers (name, country) VALUES
    ('John Smith', 'USA'),
    ('Anna Müller', 'Germany'),
    ('Kovács Péter', 'Hungary'),
    ('Sophie Martin', 'France'),
    ('James Wilson', 'UK');

INSERT INTO products (name, category, price) VALUES
    ('Laptop Pro', 'Electronics', 1299.99),
    ('Wireless Mouse', 'Electronics', 39.99),
    ('Mechanical Keyboard', 'Electronics', 129.99),
    ('Office Chair', 'Furniture', 349.99),
    ('Desk Lamp', 'Furniture', 59.99);

INSERT INTO orders (customer_id, order_date) VALUES
    (1, '2025-01-15'),
    (2, '2025-02-20'),
    (3, '2025-03-10'),
    (4, '2025-04-05'),
    (5, '2025-05-12'),
    (3, '2025-06-18'),
    (1, '2025-07-22');

INSERT INTO order_items (order_id, product_id, quantity) VALUES
    (1, 1, 2),
    (1, 2, 3),
    (2, 1, 1),
    (2, 3, 2),
    (3, 4, 1),
    (3, 5, 4),
    (4, 1, 1),
    (5, 3, 3),
    (6, 1, 2),
    (6, 2, 5),
    (7, 4, 2);
