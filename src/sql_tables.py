"""
The tables a SQL query reads, from its sqlglot parse tree.

Applied to a ground truth, this gives the tables a question needs: the
oracle schema shows exactly those, and schema retrieval is measured by
how many of them it found (table recall).
"""

import sqlglot
from sqlglot import exp


def tables_in_sql(sql: str) -> set[tuple[str, str]]:
    """
    (schema, table) pairs, lower-case; unqualified tables are in public.
    Names defined by a WITH clause are query-local, not tables.
    """
    tree = sqlglot.parse_one(sql, read="postgres")
    cte_names = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}

    tables = set()
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = table.db.lower()
        if not schema and name in cte_names:
            continue
        tables.add((schema or "public", name))

    return tables


def table_recall(gold, shown):
    """Share of the needed tables that the schema text showed (1.0 if none needed)."""
    gold = set(gold)
    if not gold:
        return 1.0
    return len(gold & set(shown)) / len(gold)


def format_tables(tables):
    """Sorted display names, matching schema.qualified_name."""
    return sorted(t if s == "public" else f"{s}.{t}" for s, t in tables)
