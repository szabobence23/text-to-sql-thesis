-- Load order follows the foreign keys. Written by database/import_bird.py.

\echo 'Importing event...'
COPY public.event FROM '/datasets/bird_student_club/data/event.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing major...'
COPY public.major FROM '/datasets/bird_student_club/data/major.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing zip_code...'
COPY public.zip_code FROM '/datasets/bird_student_club/data/zip_code.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing member...'
COPY public.member FROM '/datasets/bird_student_club/data/member.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing attendance...'
COPY public.attendance FROM '/datasets/bird_student_club/data/attendance.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing budget...'
COPY public.budget FROM '/datasets/bird_student_club/data/budget.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing expense...'
COPY public.expense FROM '/datasets/bird_student_club/data/expense.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo 'Importing income...'
COPY public.income FROM '/datasets/bird_student_club/data/income.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

ANALYZE;
