import psycopg


conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="sales_db",
    user="postgres",
    password="postgres"
)


query = """
SELECT
    tc.table_name AS table_name,
    kcu.column_name AS column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;
"""


with conn.cursor() as cur:
    cur.execute(query)
    rows = cur.fetchall()


print("Foreign key kapcsolatok:")

for row in rows:
    print(row)


conn.close()