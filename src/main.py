from schema import get_schema
from llm import generate_sql
from database import get_connection, execute_query


def main():

    # 1. PostgreSQL kapcsolat
    conn = get_connection()

    try:

        # 2. Adatbázis séma lekérése
        schema = get_schema(conn)

        # 3. Felhasználói kérdés
        question = "Melyik termékkategóriából adták el a legtöbb terméket?"

        print("Kérdés:")
        print(question)

        # 4. SQL generálása az LLM-mel
        sql = generate_sql(question, schema)

        print("\nGenerált SQL:")
        print(sql)

        # 5. SQL végrehajtása
        try:
            result = execute_query(conn, sql)

            print("\nAdatbázis eredménye:")

            if result:
                for row in result:
                    print(row)
            else:
                print("(Nincs eredmény)")

        except Exception as e:
            conn.rollback()

            print("\nSQL végrehajtási hiba:")
            print(e)

    finally:
        # 6. Kapcsolat bezárása
        conn.close()


if __name__ == "__main__":
    main()