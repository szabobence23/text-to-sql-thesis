import hashlib
import re
from dataclasses import asdict, dataclass

from ollama import chat


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
- When returning product category names, prefer the English translation table when available.
- Return ONLY the SQL query.
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


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Identifies the prompts in evaluation results, so runs with
# different prompts are never compared by accident.
PROMPT_SHA256 = _sha256(PROMPT_TEMPLATE)
CORRECTION_PROMPT_SHA256 = _sha256(CORRECTION_TEMPLATE)


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


def generate_sql(question, schema, settings: LLMSettings) -> Generation:
    prompt = PROMPT_TEMPLATE.format(schema=schema, question=question)

    return _chat([{"role": "user", "content": prompt}], settings)


def correct_sql(question, schema, failed_attempts, settings: LLMSettings) -> Generation:
    """
    Ask for a fixed query after failed attempts.

    failed_attempts: (raw_response, error) pairs, oldest first. The model
    sees every earlier attempt with its error, so it does not repeat one.
    """
    prompt = PROMPT_TEMPLATE.format(schema=schema, question=question)
    messages = [{"role": "user", "content": prompt}]

    for raw_response, error in failed_attempts:
        messages.append({"role": "assistant", "content": raw_response})
        messages.append({
            "role": "user",
            "content": CORRECTION_TEMPLATE.format(error=error),
        })

    return _chat(messages, settings)


def _chat(messages, settings: LLMSettings) -> Generation:
    response = chat(
        model=settings.model,
        messages=messages,
        options={
            "temperature": settings.temperature,
            "seed": settings.seed,
            "num_ctx": settings.num_ctx,
        },
    )

    raw = response.message.content

    return Generation(
        sql=extract_sql(raw),
        raw_response=raw,
        prompt_tokens=response.prompt_eval_count or 0,
        completion_tokens=response.eval_count or 0,
    )
