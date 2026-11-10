-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database student_club.
-- Written by database/import_bird.py.

CREATE TABLE public.event (
    event_id text NOT NULL,
    event_name text,
    event_date text,
    type text,
    notes text,
    location text,
    status text
);

CREATE TABLE public.major (
    major_id text NOT NULL,
    major_name text,
    department text,
    college text
);

CREATE TABLE public.zip_code (
    zip_code bigint NOT NULL,
    type text,
    city text,
    county text,
    state text,
    short_state text
);

CREATE TABLE public.attendance (
    link_to_event text NOT NULL,
    link_to_member text NOT NULL
);

CREATE TABLE public.budget (
    budget_id text NOT NULL,
    category text,
    spent real,
    remaining real,
    amount bigint,
    event_status text,
    link_to_event text
);

CREATE TABLE public.expense (
    expense_id text NOT NULL,
    expense_description text,
    expense_date text,
    cost real,
    approved text,
    link_to_member text,
    link_to_budget text
);

CREATE TABLE public.income (
    income_id text NOT NULL,
    date_received text,
    amount bigint,
    source text,
    notes text,
    link_to_member text
);

CREATE TABLE public.member (
    member_id text NOT NULL,
    first_name text,
    last_name text,
    email text,
    "position" text,
    t_shirt_size text,
    phone text,
    zip bigint,
    link_to_major text
);

ALTER TABLE ONLY public.event
    ADD CONSTRAINT idx_17055_sqlite_autoindex_event_1 PRIMARY KEY (event_id);
ALTER TABLE ONLY public.major
    ADD CONSTRAINT idx_17060_sqlite_autoindex_major_1 PRIMARY KEY (major_id);
ALTER TABLE ONLY public.zip_code
    ADD CONSTRAINT idx_17065_zip_code_pkey PRIMARY KEY (zip_code);
ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT idx_17070_sqlite_autoindex_attendance_1 PRIMARY KEY (link_to_event, link_to_member);
ALTER TABLE ONLY public.budget
    ADD CONSTRAINT idx_17075_sqlite_autoindex_budget_1 PRIMARY KEY (budget_id);
ALTER TABLE ONLY public.expense
    ADD CONSTRAINT idx_17080_sqlite_autoindex_expense_1 PRIMARY KEY (expense_id);
ALTER TABLE ONLY public.income
    ADD CONSTRAINT idx_17085_sqlite_autoindex_income_1 PRIMARY KEY (income_id);
ALTER TABLE ONLY public.member
    ADD CONSTRAINT idx_17090_sqlite_autoindex_member_1 PRIMARY KEY (member_id);
ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT attendance_link_to_event_fkey FOREIGN KEY (link_to_event) REFERENCES public.event(event_id);
ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT attendance_link_to_member_fkey FOREIGN KEY (link_to_member) REFERENCES public.member(member_id);
ALTER TABLE ONLY public.budget
    ADD CONSTRAINT budget_link_to_event_fkey FOREIGN KEY (link_to_event) REFERENCES public.event(event_id);
ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_link_to_budget_fkey FOREIGN KEY (link_to_budget) REFERENCES public.budget(budget_id);
ALTER TABLE ONLY public.expense
    ADD CONSTRAINT expense_link_to_member_fkey FOREIGN KEY (link_to_member) REFERENCES public.member(member_id);
ALTER TABLE ONLY public.income
    ADD CONSTRAINT income_link_to_member_fkey FOREIGN KEY (link_to_member) REFERENCES public.member(member_id);
ALTER TABLE ONLY public.member
    ADD CONSTRAINT member_link_to_major_fkey FOREIGN KEY (link_to_major) REFERENCES public.major(major_id);
ALTER TABLE ONLY public.member
    ADD CONSTRAINT member_zip_fkey FOREIGN KEY (zip) REFERENCES public.zip_code(zip_code);
