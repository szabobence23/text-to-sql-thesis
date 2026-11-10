-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing alignment...'
COPY public.alignment FROM '/datasets/bird_superhero/data/alignment.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing attribute...'
COPY public.attribute FROM '/datasets/bird_superhero/data/attribute.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing colour...'
COPY public.colour FROM '/datasets/bird_superhero/data/colour.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing gender...'
COPY public.gender FROM '/datasets/bird_superhero/data/gender.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing publisher...'
COPY public.publisher FROM '/datasets/bird_superhero/data/publisher.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing race...'
COPY public.race FROM '/datasets/bird_superhero/data/race.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing superhero...'
COPY public.superhero FROM '/datasets/bird_superhero/data/superhero.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing hero_attribute...'
COPY public.hero_attribute FROM '/datasets/bird_superhero/data/hero_attribute.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing superpower...'
COPY public.superpower FROM '/datasets/bird_superhero/data/superpower.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing hero_power...'
COPY public.hero_power FROM '/datasets/bird_superhero/data/hero_power.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
