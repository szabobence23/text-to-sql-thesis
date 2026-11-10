-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing schools...'
COPY public.schools FROM '/datasets/bird_california_schools/data/schools.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing frpm...'
COPY public.frpm FROM '/datasets/bird_california_schools/data/frpm.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing satscores...'
COPY public.satscores FROM '/datasets/bird_california_schools/data/satscores.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
