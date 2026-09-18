import psycopg

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="sales_db",
    user="postgres",
    password="postgres"
)

print("Sikeresen csatlakoztunk a PostgreSQL adatbázishoz!")

conn.close()