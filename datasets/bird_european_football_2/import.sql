-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing player...'
COPY public.player FROM '/datasets/bird_european_football_2/data/player.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing player_attributes...'
COPY public.player_attributes FROM '/datasets/bird_european_football_2/data/player_attributes.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing league...'
COPY public.league FROM '/datasets/bird_european_football_2/data/league.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing country...'
COPY public.country FROM '/datasets/bird_european_football_2/data/country.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing team...'
COPY public.team FROM '/datasets/bird_european_football_2/data/team.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing team_attributes...'
COPY public.team_attributes FROM '/datasets/bird_european_football_2/data/team_attributes.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing match...'
COPY public.match FROM '/datasets/bird_european_football_2/data/match.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
