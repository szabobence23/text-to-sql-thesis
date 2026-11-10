-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing customers...'
COPY public.customers FROM '/datasets/bird_debit_card_specializing/data/customers.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing gasstations...'
COPY public.gasstations FROM '/datasets/bird_debit_card_specializing/data/gasstations.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing products...'
COPY public.products FROM '/datasets/bird_debit_card_specializing/data/products.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing transactions_1k...'
COPY public.transactions_1k FROM '/datasets/bird_debit_card_specializing/data/transactions_1k.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing yearmonth...'
COPY public.yearmonth FROM '/datasets/bird_debit_card_specializing/data/yearmonth.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
