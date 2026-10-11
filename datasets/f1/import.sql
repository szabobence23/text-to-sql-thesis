-- Load order follows the foreign keys: lookups, races, then facts.
-- The CSVs mark missing values with \N.

\echo 'Importing seasons...'
COPY seasons FROM '/datasets/f1/data/seasons.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing circuits...'
COPY circuits FROM '/datasets/f1/data/circuits.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing drivers...'
COPY drivers FROM '/datasets/f1/data/drivers.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing constructors...'
COPY constructors FROM '/datasets/f1/data/constructors.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing status...'
COPY status FROM '/datasets/f1/data/status.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing races...'
COPY races FROM '/datasets/f1/data/races.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing results...'
COPY results FROM '/datasets/f1/data/results.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing sprint results...'
COPY sprint_results FROM '/datasets/f1/data/sprint_results.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing qualifying...'
COPY qualifying FROM '/datasets/f1/data/qualifying.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing lap times...'
COPY lap_times FROM '/datasets/f1/data/lap_times.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing pit stops...'
COPY pit_stops FROM '/datasets/f1/data/pit_stops.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing driver standings...'
COPY driver_standings FROM '/datasets/f1/data/driver_standings.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing constructor standings...'
COPY constructor_standings FROM '/datasets/f1/data/constructor_standings.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing constructor results...'
COPY constructor_results FROM '/datasets/f1/data/constructor_results.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing practice results...'
COPY practice_results FROM '/datasets/f1/data/practice_results.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing tire stints...'
COPY tire_stints FROM '/datasets/f1/data/tire_stints.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');

\echo 'Importing weather...'
COPY weather FROM '/datasets/f1/data/weather.csv'
WITH (FORMAT csv, HEADER true, NULL '\N', ENCODING 'UTF8');


-- The 2025-2026 extension left a few missing values as empty strings
-- instead of \N; store them as NULL like every other missing value.
\echo 'Normalizing empty strings to NULL...'
UPDATE drivers SET nationality = NULL WHERE nationality = '';
UPDATE drivers SET url = NULL WHERE url = '';
UPDATE qualifying SET q2 = NULL WHERE q2 = '';
UPDATE qualifying SET q3 = NULL WHERE q3 = '';

-- Every US circuit is 'USA' except the Las Vegas Strip ('United States');
-- one spelling, so a country filter finds all US races.
UPDATE circuits SET country = 'USA' WHERE country = 'United States';

ANALYZE;

\echo 'F1 import completed!'
