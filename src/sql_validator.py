from sql_structural_validator import validate_sql_structure
from sql_function_validator import validate_sql_functions
from sql_schema_validator import validate_sql_schema


def validate_sql(conn, sql: str, block_functions: bool = True) -> tuple[bool, str]:
    """
    Run structural, function-blocklist and schema validation, in order:
    the schema stage interpolates the SQL into PREPARE, so it must run
    last, after the offline stages have accepted it as a single SELECT.
    """

    # 1. Structural validation
    is_valid, error_message = validate_sql_structure(sql)

    if not is_valid:
        return False, f"Structural validation failed: {error_message}"

    # 2. Function blocklist (offline, so before touching the database)
    if block_functions:
        is_valid, error_message = validate_sql_functions(sql)

        if not is_valid:
            return False, f"Function validation failed: {error_message}"

    # 3. Schema validation
    is_valid, error_message = validate_sql_schema(conn, sql)

    if not is_valid:
        return False, f"Schema validation failed: {error_message}"

    return True, ""