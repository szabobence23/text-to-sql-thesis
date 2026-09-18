import psycopg


conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="sales_db",
    user="postgres",
    password="postgres"
)


query = """
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
"""


with conn.cursor() as cur:
    cur.execute(query)
    rows = cur.fetchall()


for row in rows:
    print(row)


conn.close()