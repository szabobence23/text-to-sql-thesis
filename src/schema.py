def get_schema(conn):
    columns_query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

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
        cur.execute(columns_query)
        columns = cur.fetchall()

        cur.execute(relationships_query)
        relationships = cur.fetchall()

    schema = "Database: olist_db\n\n"

    current_table = None

    for table_name, column_name, data_type in columns:
        if table_name != current_table:
            schema += f"Table: {table_name}\n"
            current_table = table_name

        schema += f"- {column_name} {data_type}\n"

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