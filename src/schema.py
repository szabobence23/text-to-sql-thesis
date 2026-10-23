from psycopg import sql as psql


TEXT_TYPES = ("character varying", "text", "character")
# A value longer than this is free text (a comment, a URL), not a category.
MAX_VALUE_LENGTH = 40

# Per database: the values cost one query per text column, while the
# schema text is rebuilt for every question when tables are retrieved.
_column_values_cache = {}


def fetch_column_values(conn, schemas=("public",), max_values=30):
    """
    {(schema, table, column): sorted values} for the text columns with at
    most max_values distinct non-null values, none longer than
    MAX_VALUE_LENGTH: the categories a question may name ('canceled',
    'British'), so the model writes them as the database stores them.
    """
    key = (conn.info.dbname, tuple(schemas), max_values)
    if key in _column_values_cache:
        return _column_values_cache[key]

    columns, _ = fetch_catalog(conn, schemas)
    values = {}

    with conn.cursor() as cur:
        for table_schema, table_name, column_name, data_type in columns:
            if data_type not in TEXT_TYPES:
                continue
            query = psql.SQL(
                "SELECT DISTINCT {col} FROM {tbl} WHERE {col} IS NOT NULL LIMIT %s"
            ).format(
                col=psql.Identifier(column_name),
                tbl=psql.Identifier(table_schema, table_name),
            )
            cur.execute(query, (max_values + 1,))
            found = [row[0] for row in cur.fetchall()]
            if found and len(found) <= max_values and all(len(v) <= MAX_VALUE_LENGTH for v in found):
                values[(table_schema, table_name, column_name)] = sorted(found)
    conn.rollback()

    _column_values_cache[key] = values
    return values


def _quote(value):
    return "'" + value.replace("'", "''") + "'"


def qualified_name(schema, table):
    # public tables keep their bare names, so datasets in public get
    # exactly the schema text they had before multi-schema support.
    return table if schema == "public" else f"{schema}.{table}"


def fetch_catalog(conn, schemas=("public",)):
    """
    (columns, relationships) of the base tables in the given schemas,
    read the way the application role sees them. Shared by the prompt's
    schema text and by schema retrieval, so both see the same tables.

    columns: (schema, table, column, data_type), in table and column order.
    relationships: (schema, table, column, foreign_schema, foreign_table,
    foreign_column) for every foreign key column.
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

    return columns, relationships


def get_schema(conn, database_name, hints="", schemas=("public",), tables=None, column_values=None):
    """
    Schema text for the prompt, introspected from the database.

    hints: the dataset's hand-written notes (datasets/<name>/hints.txt),
    appended after the relationships; empty for none.
    schemas: the PostgreSQL schemas to describe. Tables outside public
    are shown schema-qualified (sales.customer). Views are left out.
    tables: if given, only these (schema, table) pairs and the
    relationships between two of them; None lists every table.
    column_values: from fetch_column_values; listed after their column.
    """
    columns, relationships = fetch_catalog(conn, schemas)
    column_values = column_values or {}

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

        values = column_values.get((table_schema, table_name, column_name))
        if values:
            listed = ", ".join(_quote(v) for v in values)
            schema += f"- {column_name} {data_type} (values: {listed})\n"
        else:
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
