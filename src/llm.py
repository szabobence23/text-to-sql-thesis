from ollama import chat


def generate_sql(question, schema):
    response = chat(
        model="qwen2.5-coder:7b",
        messages=[
            {
                "role": "user",
                "content": f"""
You are an expert PostgreSQL SQL generator.

You MUST use ONLY the tables and columns defined in the schema below.

DATABASE SCHEMA:
{schema}

USER QUESTION:
{question}

Instructions:
- Generate exactly one PostgreSQL SELECT query.
- Do not invent tables.
- Do not invent columns.
- Use only tables and columns from the provided schema.
- Use the defined relationships when necessary.
- When returning product category names, prefer the English translation table when available.
- Return ONLY the SQL query.
"""
            }
        ]
    )

    sql = response.message.content.strip()

    if sql.startswith("```sql"):
        sql = sql[len("```sql"):].strip()

    if sql.endswith("```"):
        sql = sql[:-3].strip()

    return sql