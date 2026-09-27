from sql_structural_validator import validate_sql_structure
from sql_schema_validator import validate_sql_schema


def validate_sql(conn, sql: str) -> tuple[bool, str]:
    """
    Run structural and schema validation.
    """

    # 1. Structural validation
    is_valid, error_message = validate_sql_structure(sql)

    if not is_valid:
        return False, f"Structural validation failed: {error_message}"

    # 2. Schema validation
    is_valid, error_message = validate_sql_schema(conn, sql)

    if not is_valid:
        return False, f"Schema validation failed: {error_message}"

    return True, ""