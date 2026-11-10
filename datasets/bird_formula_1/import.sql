-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing circuits...'
COPY public.circuits FROM '/datasets/bird_formula_1/data/circuits.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing constructors...'
COPY public.constructors FROM '/datasets/bird_formula_1/data/constructors.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing drivers...'
COPY public.drivers FROM '/datasets/bird_formula_1/data/drivers.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing seasons...'
COPY public.seasons FROM '/datasets/bird_formula_1/data/seasons.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing races...'
COPY public.races FROM '/datasets/bird_formula_1/data/races.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing constructorresults...'
COPY public.constructorresults FROM '/datasets/bird_formula_1/data/constructorresults.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing constructorstandings...'
COPY public.constructorstandings FROM '/datasets/bird_formula_1/data/constructorstandings.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing driverstandings...'
COPY public.driverstandings FROM '/datasets/bird_formula_1/data/driverstandings.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing laptimes...'
COPY public.laptimes FROM '/datasets/bird_formula_1/data/laptimes.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing pitstops...'
COPY public.pitstops FROM '/datasets/bird_formula_1/data/pitstops.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing qualifying...'
COPY public.qualifying FROM '/datasets/bird_formula_1/data/qualifying.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing status...'
COPY public.status FROM '/datasets/bird_formula_1/data/status.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing results...'
COPY public.results FROM '/datasets/bird_formula_1/data/results.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
