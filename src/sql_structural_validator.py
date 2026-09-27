import sqlglot
from sqlglot import exp


def validate_sql_structure(sql: str) -> tuple[bool, str]:
    """
    Check SQL structure before sending it to PostgreSQL.

    Allows exactly one SELECT or WITH ... SELECT query.
    """

    if not sql or not sql.strip():
        return False, "Empty SQL query."

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        return False, f"SQL syntax error: {e}"

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        return False, "Only one SQL statement is allowed."

    tree = statements[0]

    # SELECT and WITH ... SELECT are Query nodes.
    if not isinstance(tree, exp.Query):
        return False, "Only SELECT queries are allowed."

    forbidden_types = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
    )

    for node in tree.walk():
        if isinstance(node, forbidden_types):
            return False, (
                f"Forbidden SQL operation: "
                f"{type(node).__name__}"
            )

    if any(tree.find_all(exp.Into)):
        return False, "SELECT INTO is not allowed."

    if any(tree.find_all(exp.Lock)):
        return False, "SQL locking clauses are not allowed."

    return True, ""
