-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing molecule...'
COPY public.molecule FROM '/datasets/bird_toxicology/data/molecule.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing atom...'
COPY public.atom FROM '/datasets/bird_toxicology/data/atom.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing bond...'
COPY public.bond FROM '/datasets/bird_toxicology/data/bond.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing connected...'
COPY public.connected FROM '/datasets/bird_toxicology/data/connected.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
