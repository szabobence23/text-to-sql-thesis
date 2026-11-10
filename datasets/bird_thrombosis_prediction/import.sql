-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing patient...'
COPY public.patient FROM '/datasets/bird_thrombosis_prediction/data/patient.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing examination...'
COPY public.examination FROM '/datasets/bird_thrombosis_prediction/data/examination.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing laboratory...'
COPY public.laboratory FROM '/datasets/bird_thrombosis_prediction/data/laboratory.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
