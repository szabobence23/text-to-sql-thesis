-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing cards...'
COPY public.cards FROM '/datasets/bird_card_games/data/cards.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing foreign_data...'
COPY public.foreign_data FROM '/datasets/bird_card_games/data/foreign_data.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing legalities...'
COPY public.legalities FROM '/datasets/bird_card_games/data/legalities.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing sets...'
COPY public.sets FROM '/datasets/bird_card_games/data/sets.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing set_translations...'
COPY public.set_translations FROM '/datasets/bird_card_games/data/set_translations.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing rulings...'
COPY public.rulings FROM '/datasets/bird_card_games/data/rulings.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
