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
    schema = "Database: olist_db\n\n"

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

    schema += """
Important notes:
- product_category_name contains the original Portuguese product category names.
- product_category_name_translation maps product_category_name to English using product_category_name_english.
- When returning product category names, prefer product_category_name_english when available.
"""

    return schema


# 1. PostgreSQL kapcsolat

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="olist_db",
    user="postgres",
    password="postgres"
)


# 2. Schema automatikus lekérése

schema = get_schema(conn)

print("Adatbázis séma:")
print(schema)


# 3. Tesztkérdések

questions = [
    "Hány rendelés van az adatbázisban?",
    "Hány törölt rendelés van?",
    "Mennyi az átlagos termékár?",
    "Melyik államból származik a legtöbb vásárló?",
    "Melyik eladó értékesítette a legtöbb terméket?",
    "Melyik termékkategóriából származott a legtöbb eladás?",
    "Hány rendelés történt 2017 januárjában?",
    "Melyik az 5 legdrágább termék?",
    "Melyik vásárló adta le a legtöbb rendelést?",
    "Melyik termékből származott a legtöbb bevétel?"
]


# 4. Eredmények fájl megnyitása

with open("evaluation_results.txt", "w", encoding="utf-8") as file:

    for i, question in enumerate(questions, start=1):

        separator = "=" * 80

        # ---------------------------------------------------------
        # Teszt fejléc
        # ---------------------------------------------------------

        print("\n" + separator)
        print(f"TESZT {i}")
        print(separator)

        print("\nKérdés:")
        print(question)

        file.write("\n" + separator + "\n")
        file.write(f"TESZT {i}\n")
        file.write(separator + "\n\n")

        file.write("Kérdés:\n")
        file.write(question + "\n\n")


        # SQL generálása 

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
- When returning product category names, prefer the English translation table when available.
- Return ONLY the SQL query.
"""
                }
            ]
        )

        # LLM válaszának megtisztítása

        sql = response.message.content.strip()

        if sql.startswith("```sql"):
            sql = sql[len("```sql"):].strip()

        if sql.endswith("```"):
            sql = sql[:-3].strip()


        # SQL kiírása

        print("\nGenerált SQL:")
        print(sql)

        file.write("Generált SQL:\n")
        file.write(sql + "\n\n")


        # SQL végrehajtása

        try:

            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchall()


            # Eredmény

            print("\nAdatbázis eredménye:")

            if result:
                for row in result:
                    print(row)
            else:
                print("(Nincs eredmény)")

            file.write("Adatbázis eredménye:\n")

            if result:
                for row in result:
                    file.write(str(row) + "\n")
            else:
                file.write("(Nincs eredmény)\n")

            file.write("\n")

        except Exception as e:

            # SQL hiba esetén ne álljon le az egész tesztelés
            print("\nHIBA az SQL végrehajtásakor:")
            print(e)

            file.write("HIBA az SQL végrehajtásakor:\n")
            file.write(str(e) + "\n\n")

            conn.rollback()


# PostgreSQL kapcsolat bezárása

conn.close()

print("\n" + "=" * 80)
print("A tesztelés befejeződött.")
print("Eredmények mentve: evaluation_results.txt")
print("=" * 80)