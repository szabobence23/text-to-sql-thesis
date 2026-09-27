def get_schema(conn, database_name, hints=""):
    """
    Schema text for the prompt, introspected from the database.

    hints: the dataset's hand-written notes (datasets/<name>/hints.txt),
    appended after the relationships; empty for none.
    """
    columns_query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

    # pg_catalog instead of information_schema: constraint_column_usage
    # only shows constraints to the table owner, so the read-only
    # application role would see no relationships at all.
    relationships_query = """
    SELECT
        cl.relname AS table_name,
        a.attname AS column_name,
        fcl.relname AS foreign_table_name,
        fa.attname AS foreign_column_name
    FROM pg_constraint AS c
    JOIN pg_class AS cl ON cl.oid = c.conrelid
    JOIN pg_namespace AS n ON n.oid = cl.relnamespace
    JOIN pg_class AS fcl ON fcl.oid = c.confrelid
    CROSS JOIN LATERAL unnest(c.conkey, c.confkey) AS k(attnum, fattnum)
    JOIN pg_attribute AS a
        ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    JOIN pg_attribute AS fa
        ON fa.attrelid = c.confrelid AND fa.attnum = k.fattnum
    WHERE c.contype = 'f'
        AND n.nspname = 'public'
    ORDER BY table_name, column_name;
    """

    with conn.cursor() as cur:
        cur.execute(columns_query)
        columns = cur.fetchall()

        cur.execute(relationships_query)
        relationships = cur.fetchall()

    conn.rollback()

    schema = f"Database: {database_name}\n\n"

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

    if hints:
        schema += f"\n{hints}\n"

    return schema