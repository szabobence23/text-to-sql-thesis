def qualified_name(schema, table):
    # public tables keep their bare names, so datasets in public get
    # exactly the schema text they had before multi-schema support.
    return table if schema == "public" else f"{schema}.{table}"


def get_schema(conn, database_name, hints="", schemas=("public",), tables=None):
    """
    Schema text for the prompt, introspected from the database.

    hints: the dataset's hand-written notes (datasets/<name>/hints.txt),
    appended after the relationships; empty for none.
    schemas: the PostgreSQL schemas to describe. Tables outside public
    are shown schema-qualified (sales.customer). Views are left out.
    tables: if given, only these (schema, table) pairs and the
    relationships between two of them; None lists every table.
    """
    columns_query = """
    SELECT c.table_schema, c.table_name, c.column_name, c.data_type
    FROM information_schema.columns AS c
    JOIN information_schema.tables AS t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name
    WHERE c.table_schema = ANY(%(schemas)s)
        AND t.table_type = 'BASE TABLE'
    ORDER BY c.table_schema, c.table_name, c.ordinal_position;
    """

    # pg_catalog instead of information_schema: constraint_column_usage
    # only shows constraints to the table owner, so the read-only
    # application role would see no relationships at all.
    relationships_query = """
    SELECT
        n.nspname AS table_schema,
        cl.relname AS table_name,
        a.attname AS column_name,
        fn.nspname AS foreign_table_schema,
        fcl.relname AS foreign_table_name,
        fa.attname AS foreign_column_name
    FROM pg_constraint AS c
    JOIN pg_class AS cl ON cl.oid = c.conrelid
    JOIN pg_namespace AS n ON n.oid = cl.relnamespace
    JOIN pg_class AS fcl ON fcl.oid = c.confrelid
    JOIN pg_namespace AS fn ON fn.oid = fcl.relnamespace
    CROSS JOIN LATERAL unnest(c.conkey, c.confkey) AS k(attnum, fattnum)
    JOIN pg_attribute AS a
        ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    JOIN pg_attribute AS fa
        ON fa.attrelid = c.confrelid AND fa.attnum = k.fattnum
    WHERE c.contype = 'f'
        AND n.nspname = ANY(%(schemas)s)
    ORDER BY table_schema, table_name, column_name;
    """

    params = {"schemas": list(schemas)}

    with conn.cursor() as cur:
        cur.execute(columns_query, params)
        columns = cur.fetchall()

        cur.execute(relationships_query, params)
        relationships = cur.fetchall()

    conn.rollback()

    if tables is not None:
        wanted = {(s.lower(), t.lower()) for s, t in tables}
        columns = [c for c in columns if (c[0], c[1]) in wanted]
        relationships = [
            r for r in relationships
            if (r[0], r[1]) in wanted and (r[3], r[4]) in wanted
        ]

    schema = f"Database: {database_name}\n\n"

    current_table = None

    for table_schema, table_name, column_name, data_type in columns:
        table = qualified_name(table_schema, table_name)

        if table != current_table:
            schema += f"Table: {table}\n"
            current_table = table

        schema += f"- {column_name} {data_type}\n"

    schema += "\nRelationships:\n"

    for (table_schema, table_name, column_name,
         foreign_schema, foreign_table, foreign_column) in relationships:
        schema += (
            f"- {qualified_name(table_schema, table_name)}.{column_name} "
            f"-> {qualified_name(foreign_schema, foreign_table)}.{foreign_column}\n"
        )

    if hints:
        schema += f"\n{hints}\n"

    return schema
