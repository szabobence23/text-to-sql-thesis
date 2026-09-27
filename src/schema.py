# Hand-written, Olist-specific knowledge appended to the schema text.
# Switchable via PipelineConfig.schema_hints, so its effect is measurable.
SCHEMA_HINTS = """
Important notes:
- product_category_name contains the original Portuguese product category names.
- product_category_name_translation maps product_category_name to English using product_category_name_english.
- When returning product category names, prefer product_category_name_english when available.
"""


def get_schema(conn, include_hints=True):
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

    if include_hints:
        schema += SCHEMA_HINTS

    return schema