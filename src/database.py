import psycopg


def get_connection():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="olist_db",
        user="postgres",
        password="postgres"
    )


def execute_query(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()