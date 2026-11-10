-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing district...'
COPY public.district FROM '/datasets/bird_financial/data/district.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing account...'
COPY public.account FROM '/datasets/bird_financial/data/account.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing client...'
COPY public.client FROM '/datasets/bird_financial/data/client.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing disp...'
COPY public.disp FROM '/datasets/bird_financial/data/disp.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing card...'
COPY public.card FROM '/datasets/bird_financial/data/card.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing loan...'
COPY public.loan FROM '/datasets/bird_financial/data/loan.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing order...'
COPY public."order" FROM '/datasets/bird_financial/data/order.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing trans...'
COPY public.trans FROM '/datasets/bird_financial/data/trans.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
