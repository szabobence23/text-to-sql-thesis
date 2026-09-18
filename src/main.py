from ollama import chat
import psycopg


def get_schema(conn):
    # Táblák és oszlopok lekérése
    columns_query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

    # Foreign key kapcsolatok lekérése
    relationships_query = """
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
        # Oszlopok
        cur.execute(columns_query)
        columns = cur.fetchall()

        # Kapcsolatok
        cur.execute(relationships_query)
        relationships = cur.fetchall()

    # Schema szöveg felépítése
    schema = "Database: sales_db\n\n"

    current_table = None

    for table_name, column_name, data_type in columns:

        if table_name != current_table:
            schema += f"Table: {table_name}\n"
            current_table = table_name

        schema += f"- {column_name} {data_type}\n"

    # Kapcsolatok hozzáadása
    schema += "\nRelationships:\n"

    for table_name, column_name, foreign_table, foreign_column in relationships:
        schema += (
            f"- {table_name}.{column_name} "
            f"-> {foreign_table}.{foreign_column}\n"
        )

    return schema


# 1. PostgreSQL kapcsolat

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="sales_db",
    user="postgres",
    password="postgres"
)


# 2. Schema automatikus lekérése

schema = get_schema(conn)

print("Adatbázis séma:")
print(schema)


# 3. Felhasználói kérdés

question = "Mennyi volt a rendelések száma 2025 márciusában?"


# 4. SQL generálása az LLM-mel

response = chat(
    model="qwen2.5-coder:7b",
    messages=[
        {
            "role": "user",
            "content": f"""
You are an expert PostgreSQL SQL generator.

You MUST use ONLY the tables and columns defined in the schema below.

DATABASE SCHEMA:
{schema}

USER QUESTION:
{question}

Instructions:
- Generate exactly one PostgreSQL SELECT query.
- Do not invent tables.
- Do not invent columns.
- Use only tables and columns from the provided schema.
- Use the defined relationships when necessary.
- Return ONLY the SQL query.
"""
        }
    ]
)


# 5. LLM válaszának megtisztítása

sql = response.message.content.strip()

if sql.startswith("```sql"):
    sql = sql[len("```sql"):].strip()

if sql.endswith("```"):
    sql = sql[:-3].strip()


print("Generált SQL:")
print(sql)


# 6. SQL végrehajtása

with conn.cursor() as cur:
    cur.execute(sql)
    result = cur.fetchall()


# 7. Eredmény

print("\nAdatbázis eredménye:")

for row in result:
    print(row)


conn.close()