import hashlib
import re
from dataclasses import asdict, dataclass

import ollama
from ollama import chat


# Dataset-independent: guidance for one dataset belongs in its
# datasets/<name>/hints.txt, which is part of {schema}.
PROMPT_TEMPLATE = """
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
- Return ONLY the SQL query.
"""

# Optional block of the SQL prompt (pipeline: sql_examples, dynamic
# few-shot): solved questions similar to this one, with their SQL, just
# before the question. Inserted only when there are examples, so
# PROMPT_TEMPLATE and its hash stay as they were.
SQL_EXAMPLES_BLOCK = """
EXAMPLES (solved questions for this database; follow their patterns, but answer the USER QUESTION):

{examples}
"""

# Sent after a failed attempt, continuing the same conversation, so the
# first-attempt prompt stays identical to the baseline.
CORRECTION_TEMPLATE = """
The SQL query above failed with this PostgreSQL error:

{error}

Fix the query so that it answers the original question.
Use only tables and columns from the schema.
Return ONLY the corrected SQL query.
"""

# After successful execution the rows are turned into an answer in two
# separate conversations. The model only sees the result, so a wrong
# query would give a fluent but wrong answer (it presented one of 17
# race leaders as the 2007 world champion):
# 1. RESULT_CHECK_TEMPLATE asks for a one-word verdict on whether the
#    result answers the question. A single verdict with concrete cases
#    worked best; asked as separate fields, or together with writing the
#    answer, the 7B model fitted its judgement to the rows (13 hand-made
#    cases, 5 wrong results: all flagged, no false alarm).
# 2. ANSWER_TEMPLATE writes the answer from the result only; a doubtful
#    result gets DOUBT_NOTE, so the answer says so instead of presenting
#    one row as the answer.
RESULT_CHECK_TEMPLATE = """
You check whether a database query result answers a user's question. The query
was generated automatically and may be wrong.

QUESTION:
{question}

QUERY RESULT ({row_info}):
{result}

It is DOUBTFUL if any of these holds:
- The question asks for a single winner, person or item (for example "who won", "which is the most"), but the result lists several different names or items.
- The result does not contain the kind of data the question asks for (for example names for "who", a price for "how expensive", an age for "how old").
- The values are implausible.
Otherwise it is OK. A question asking for a top N, a list or a value per group is OK with several rows.

Reply with one word: OK or DOUBTFUL.
"""

ANSWER_TEMPLATE = """
A user asked a question about a database. The SQL query below was run to answer it.

USER QUESTION:
{question}

SQL QUERY:
{sql}

QUERY RESULT ({row_info}):
{result}
{note}
Instructions:
- Answer the user's question based ONLY on the query result above.
- Write the answer in the same language as the user's question.
- Never add facts from your own knowledge, even if you know the true answer. Do not add units or currencies that are not in the result.
- Be concise. If there are many rows, summarize them or list the most important ones.
- If the result is empty, say that no matching data was found.
- Do not mention SQL, tables or columns unless it is necessary.
"""

DOUBT_NOTE = """
NOTE: A check found that this result may not answer the question. Say so plainly
in your answer, describe in one sentence what the result contains, and do not
present any single row as the answer.
"""


def check_verdict(text):
    """The reply to RESULT_CHECK_TEMPLATE: True = DOUBTFUL, False = OK, None = neither."""
    words = re.findall(r"[A-Za-z]+", text.upper())
    if "DOUBTFUL" in words:
        return True
    if "OK" in words:
        return False
    return None


# Optional step before schema retrieval: the tables are described in
# English, so an English question finds them more easily. Applied to
# every question, since the system does not know its language.
TRANSLATE_TEMPLATE = """
Translate the user's database question into English.

QUESTION:
{question}

Instructions:
- If the question is already in English, return it unchanged.
- Keep names, numbers and quoted values exactly as they are.
- Do not answer the question and do not write SQL.
- Return ONLY the English question.
"""


# Optional step after schema retrieval (schema linking): the model keeps
# only the candidate tables the query needs, so the SQL prompt has fewer
# distracting tables. It sees table and column names, not the data.
TABLE_SELECTION_TEMPLATE = """
You are choosing the database tables needed to answer a question with SQL.

QUESTION:
{question}

CANDIDATE TABLES:
{tables}

Instructions:
- Choose every table the SQL query needs, including tables used only to join other tables.
- Leave out the tables the query does not need.
- Use only table names from the list above.
- Return ONLY the chosen table names, one per line.
"""

# A variant that errs towards keeping tables: the strict prompt dropped
# needed tables (similar-looking tables, tables holding names), and a
# missing table makes a correct query impossible, an extra one rarely does.
TABLE_SELECTION_INCLUSIVE_TEMPLATE = """
You are choosing the database tables needed to answer a question with SQL.

QUESTION:
{question}

CANDIDATE TABLES:
{tables}

Instructions:
- Choose every table the SQL query needs, including tables used only to join other tables.
- If the answer should show names or other descriptive values, keep the table that stores them.
- When you are not sure whether a table is needed, keep it: a missing table makes the query impossible, an extra one does little harm.
- Leave out the tables that are clearly unrelated to the question.
- Use only table names from the list above.
- Return ONLY the chosen table names, one per line.
"""

TABLE_SELECTION_TEMPLATES = {
    "strict": TABLE_SELECTION_TEMPLATE,
    "inclusive": TABLE_SELECTION_INCLUSIVE_TEMPLATE,
}

# Optional block of the table-selection prompt: solved questions similar
# to this one and the tables their SQL read (examples.py). Inserted
# before the candidate list only when there are examples, so the
# selection templates, and their hashes, stay as they were.
TABLE_SELECTION_EXAMPLES_BLOCK = """
SIMILAR SOLVED QUESTIONS AND THE TABLES THEIR SQL USED (a guide, not the answer):
{examples}
"""


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Identifies the prompts in evaluation results, so runs with
# different prompts are never compared by accident.
PROMPT_SHA256 = _sha256(PROMPT_TEMPLATE)
CORRECTION_PROMPT_SHA256 = _sha256(CORRECTION_TEMPLATE)
ANSWER_PROMPT_SHA256 = _sha256(RESULT_CHECK_TEMPLATE + ANSWER_TEMPLATE + DOUBT_NOTE)
TRANSLATE_PROMPT_SHA256 = _sha256(TRANSLATE_TEMPLATE)
TABLE_SELECTION_PROMPT_SHA256 = _sha256(TABLE_SELECTION_TEMPLATE)
TABLE_SELECTION_PROMPT_SHA256S = {
    style: _sha256(template) for style, template in TABLE_SELECTION_TEMPLATES.items()
}
TABLE_SELECTION_EXAMPLES_SHA256 = _sha256(TABLE_SELECTION_EXAMPLES_BLOCK)
SQL_EXAMPLES_SHA256 = _sha256(SQL_EXAMPLES_BLOCK)


def model_digest(model):
    """
    The digest of a pulled Ollama model. A tag (qwen2.5-coder:7b, bge-m3)
    can point to new weights after a re-pull; the digest identifies the
    exact model. None if the model is not pulled.
    """
    names = {model, f"{model}:latest"}
    for m in ollama.list().models:
        if m.model in names:
            return m.digest
    return None


@dataclass(frozen=True)
class LLMSettings:
    model: str = "qwen2.5-coder:7b"
    # temperature 0 + fixed seed: repeated runs give the same SQL,
    # so differences between configurations are not sampling noise.
    temperature: float = 0.0
    seed: int = 42
    # Ollama silently truncates prompts longer than num_ctx,
    # so the context size is set explicitly instead of the default.
    num_ctx: int = 8192

    def to_dict(self):
        return asdict(self)


@dataclass
class Generation:
    sql: str
    raw_response: str
    prompt_tokens: int
    completion_tokens: int


_CODE_BLOCK = re.compile(r"```[a-zA-Z]*\s*\n?(.*?)```", re.DOTALL)


def extract_sql(text: str) -> str:
    """
    Get the SQL out of a model response.

    Takes the first fenced code block if there is one (with or
    without a language tag), otherwise the whole response.
    """
    match = _CODE_BLOCK.search(text)
    if match:
        return match.group(1).strip()

    return text.strip()


def sql_prompt(question, schema, examples_text=None):
    """The SQL prompt; examples_text (solved examples) goes before the question."""
    prompt = PROMPT_TEMPLATE.format(schema=schema, question=question)
    if examples_text:
        block = SQL_EXAMPLES_BLOCK.format(examples=examples_text)
        prompt = prompt.replace("\nUSER QUESTION:", block + "\nUSER QUESTION:", 1)
    return prompt


def generate_sql(question, schema, settings: LLMSettings, examples_text=None) -> Generation:
    prompt = sql_prompt(question, schema, examples_text)

    return _chat([{"role": "user", "content": prompt}], settings)


def correct_sql(question, schema, failed_attempts, settings: LLMSettings, examples_text=None) -> Generation:
    """
    Ask for a fixed query after failed attempts.

    failed_attempts: (raw_response, error) pairs, oldest first. The model
    sees every earlier attempt with its error, so it does not repeat one.
    The first message is the same prompt as the first attempt's.
    """
    prompt = sql_prompt(question, schema, examples_text)
    messages = [{"role": "user", "content": prompt}]

    for raw_response, error in failed_attempts:
        messages.append({"role": "assistant", "content": raw_response})
        messages.append({
            "role": "user",
            "content": CORRECTION_TEMPLATE.format(error=error),
        })

    return _chat(messages, settings)


@dataclass
class Answer:
    text: str
    prompt_tokens: int
    completion_tokens: int
    # The result check (RESULT_CHECK_TEMPLATE): True if the result may not
    # answer the question, None if the check gave no verdict.
    doubtful: bool | None = None


def format_result(columns, rows, max_rows):
    """
    The query result as text for the answer prompt: a header line and
    at most max_rows rows, so a large result cannot overflow num_ctx.
    """
    shown = rows[:max_rows]

    if not rows:
        row_info = "0 rows"
    elif len(rows) > max_rows:
        row_info = f"first {max_rows} of {len(rows)} rows"
    elif len(rows) == 1:
        row_info = "1 row"
    else:
        row_info = f"{len(rows)} rows"

    def cell(value):
        return "NULL" if value is None else str(value)

    lines = [" | ".join(columns)]
    lines += [" | ".join(cell(value) for value in row) for row in shown]

    return row_info, "\n".join(lines)


def generate_answer(question, sql, columns, rows, max_rows, settings: LLMSettings) -> Answer:
    row_info, result = format_result(columns, rows, max_rows)

    check = _call(
        [{"role": "user", "content": RESULT_CHECK_TEMPLATE.format(
            question=question, row_info=row_info, result=result,
        )}],
        settings,
    )
    doubtful = check_verdict(check.message.content)

    prompt = ANSWER_TEMPLATE.format(
        question=question, sql=sql, row_info=row_info, result=result,
        note=DOUBT_NOTE if doubtful else "",
    )
    response = _call([{"role": "user", "content": prompt}], settings)

    return Answer(
        text=response.message.content.strip(),
        prompt_tokens=(response.prompt_eval_count or 0) + (check.prompt_eval_count or 0),
        completion_tokens=(response.eval_count or 0) + (check.eval_count or 0),
        doubtful=doubtful,
    )


@dataclass
class Translation:
    text: str
    prompt_tokens: int
    completion_tokens: int


def translate_question(question, settings: LLMSettings) -> Translation:
    prompt = TRANSLATE_TEMPLATE.format(question=question)
    response = _call([{"role": "user", "content": prompt}], settings)

    # Models sometimes wrap the answer in quotes or a code fence.
    text = extract_sql(response.message.content).strip().strip('"').strip()

    return Translation(
        text=text or question,
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
    )


@dataclass
class TableSelection:
    text: str  # the model's raw answer; retrieval.parse_table_choice reads it
    prompt_tokens: int
    completion_tokens: int


def choose_tables(question, tables_text, settings: LLMSettings, style="strict",
                  examples_text=None) -> TableSelection:
    # examples_text: one line per similar solved question, or None.
    prompt = TABLE_SELECTION_TEMPLATES[style].format(question=question, tables=tables_text)
    if examples_text:
        block = TABLE_SELECTION_EXAMPLES_BLOCK.format(examples=examples_text)
        prompt = prompt.replace("\nCANDIDATE TABLES:", block + "\nCANDIDATE TABLES:", 1)
    response = _call([{"role": "user", "content": prompt}], settings)

    return TableSelection(
        text=response.message.content,
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
    )


def _call(messages, settings: LLMSettings):
    return chat(
        model=settings.model,
        messages=messages,
        options={
            "temperature": settings.temperature,
            "seed": settings.seed,
            "num_ctx": settings.num_ctx,
        },
    )


def _chat(messages, settings: LLMSettings) -> Generation:
    response = _call(messages, settings)

    raw = response.message.content

    return Generation(
        sql=extract_sql(raw),
        raw_response=raw,
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
    )
