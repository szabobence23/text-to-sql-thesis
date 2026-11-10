-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database debit_card_specializing.
-- Written by database/import_bird.py.

CREATE TABLE public.customers (
    customerid bigint NOT NULL,
    segment text,
    currency text
);

CREATE TABLE public.gasstations (
    gasstationid bigint NOT NULL,
    chainid bigint,
    country text,
    segment text
);

CREATE TABLE public.products (
    productid bigint NOT NULL,
    description text
);

CREATE TABLE public.transactions_1k (
    transactionid bigint NOT NULL,
    date date,
    "time" text,
    customerid bigint,
    cardid bigint,
    gasstationid bigint,
    productid bigint,
    amount bigint,
    price real
);

CREATE TABLE public.yearmonth (
    customerid bigint,
    date text,
    consumption real
);

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT idx_47287_customers_pkey PRIMARY KEY (customerid);
ALTER TABLE ONLY public.gasstations
    ADD CONSTRAINT idx_47292_gasstations_pkey PRIMARY KEY (gasstationid);
ALTER TABLE ONLY public.products
    ADD CONSTRAINT idx_47297_products_pkey PRIMARY KEY (productid);
ALTER TABLE ONLY public.transactions_1k
    ADD CONSTRAINT idx_47303_transactions_1k_pkey PRIMARY KEY (transactionid);
CREATE UNIQUE INDEX idx_47287_sqlite_autoindex_customers_1 ON public.customers USING btree (customerid);
CREATE UNIQUE INDEX idx_47292_sqlite_autoindex_gasstations_1 ON public.gasstations USING btree (gasstationid);
CREATE UNIQUE INDEX idx_47297_sqlite_autoindex_products_1 ON public.products USING btree (productid);
CREATE UNIQUE INDEX idx_47309_sqlite_autoindex_yearmonth_1 ON public.yearmonth USING btree (date, customerid);
