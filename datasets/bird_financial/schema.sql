-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database financial.
-- Written by database/import_bird.py.

CREATE TABLE public.account (
    account_id bigint DEFAULT '0'::bigint NOT NULL,
    district_id bigint DEFAULT '0'::bigint,
    frequency text,
    date date
);

CREATE TABLE public.card (
    card_id bigint DEFAULT '0'::bigint NOT NULL,
    disp_id bigint,
    type text,
    issued date
);

CREATE TABLE public.client (
    client_id bigint NOT NULL,
    gender text,
    birth_date date,
    district_id bigint
);

CREATE TABLE public.disp (
    disp_id bigint NOT NULL,
    client_id bigint,
    account_id bigint,
    type text
);

CREATE TABLE public.district (
    district_id bigint DEFAULT '0'::bigint NOT NULL,
    a2 text,
    a3 text,
    a4 text,
    a5 text,
    a6 text,
    a7 text,
    a8 bigint,
    a9 bigint,
    a10 real,
    a11 bigint,
    a12 real,
    a13 real,
    a14 bigint,
    a15 bigint,
    a16 bigint
);

CREATE TABLE public.loan (
    loan_id bigint DEFAULT '0'::bigint NOT NULL,
    account_id bigint,
    date date,
    amount bigint,
    duration bigint,
    payments real,
    status text
);

CREATE TABLE public."order" (
    order_id bigint DEFAULT '0'::bigint NOT NULL,
    account_id bigint,
    bank_to text,
    account_to bigint,
    amount real,
    k_symbol text
);

CREATE TABLE public.trans (
    trans_id bigint DEFAULT '0'::bigint NOT NULL,
    account_id bigint DEFAULT '0'::bigint,
    date date,
    type text,
    operation text,
    amount bigint,
    balance bigint,
    k_symbol text,
    bank text,
    account bigint
);

ALTER TABLE ONLY public.account
    ADD CONSTRAINT idx_17818_account_pkey PRIMARY KEY (account_id);
ALTER TABLE ONLY public.card
    ADD CONSTRAINT idx_17825_card_pkey PRIMARY KEY (card_id);
ALTER TABLE ONLY public.client
    ADD CONSTRAINT idx_17831_client_pkey PRIMARY KEY (client_id);
ALTER TABLE ONLY public.disp
    ADD CONSTRAINT idx_17836_disp_pkey PRIMARY KEY (disp_id);
ALTER TABLE ONLY public.district
    ADD CONSTRAINT idx_17841_district_pkey PRIMARY KEY (district_id);
ALTER TABLE ONLY public.loan
    ADD CONSTRAINT idx_17847_loan_pkey PRIMARY KEY (loan_id);
ALTER TABLE ONLY public."order"
    ADD CONSTRAINT idx_17853_order_pkey PRIMARY KEY (order_id);
ALTER TABLE ONLY public.trans
    ADD CONSTRAINT idx_17859_trans_pkey PRIMARY KEY (trans_id);
ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_district_id_fkey FOREIGN KEY (district_id) REFERENCES public.district(district_id);
ALTER TABLE ONLY public.card
    ADD CONSTRAINT card_disp_id_fkey FOREIGN KEY (disp_id) REFERENCES public.disp(disp_id);
ALTER TABLE ONLY public.client
    ADD CONSTRAINT client_district_id_fkey FOREIGN KEY (district_id) REFERENCES public.district(district_id);
ALTER TABLE ONLY public.disp
    ADD CONSTRAINT disp_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(account_id);
ALTER TABLE ONLY public.disp
    ADD CONSTRAINT disp_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.client(client_id);
ALTER TABLE ONLY public.loan
    ADD CONSTRAINT loan_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(account_id);
ALTER TABLE ONLY public."order"
    ADD CONSTRAINT order_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(account_id);
ALTER TABLE ONLY public.trans
    ADD CONSTRAINT trans_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(account_id);
