-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing users...'
COPY public.users FROM '/datasets/bird_codebase_community/data/users.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing badges...'
COPY public.badges FROM '/datasets/bird_codebase_community/data/badges.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing comments...'
COPY public.comments FROM '/datasets/bird_codebase_community/data/comments.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing posthistory...'
COPY public.posthistory FROM '/datasets/bird_codebase_community/data/posthistory.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing postlinks...'
COPY public.postlinks FROM '/datasets/bird_codebase_community/data/postlinks.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing posts...'
COPY public.posts FROM '/datasets/bird_codebase_community/data/posts.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing tags...'
COPY public.tags FROM '/datasets/bird_codebase_community/data/tags.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing votes...'
COPY public.votes FROM '/datasets/bird_codebase_community/data/votes.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
