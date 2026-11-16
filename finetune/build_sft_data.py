"""
Build the supervised fine-tuning data from the checked BIRD train gold SQL
(finetune/data/bird_train_gold.json, written by transpile_gold.py): one
chat per question, in the exact form the model gets at test time.

    python finetune/build_sft_data.py [--seed 0] [--valid-databases 5]
        [--evidence-share 0.5] [--examples-share 0.3]

- system: the Ollama model's own system prompt (checked against
  `ollama show`), which its chat template sends with every request;
- user: llm.sql_prompt with the schema text of schema.get_schema, i.e.
  byte for byte the prompt the pipeline builds;
- assistant: the PostgreSQL query as the base model answers, a ```sql
  block with the query laid out over several lines (sqlglot pretty; the
  parsed query is checked to be the same as the verified one).

Kept: status ok with a non-empty SQLite result (an empty result shows
little). Drawn per question with the fixed seed:
- evidence: shown (EVIDENCE_BLOCK) for evidence_share of the questions
  that have one; our own test sets have no evidence, BIRD Mini-Dev has.
- examples: examples_share of the questions get 3 or 5 solved questions of
  the same database (SQL_EXAMPLES_BLOCK, format_sql_examples), the most
  similar by bge-m3 as examples.ExampleRetriever ranks them, for the
  few-shot setups. Never the question itself, one with the same SQL, or
  one with similarity >= 0.9 (the limit the test sets' example pools
  keep), so an example never gives the answer away.
Validation: valid_databases whole databases, drawn with the seed, so the
validation loss is measured on unseen databases, like the tests.

Writes finetune/data/sft/train.jsonl, valid.jsonl and meta.json (counts,
settings, prompt hashes, input hashes, git commit).
"""

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict

import ollama
import sqlglot

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FINETUNE_DIR)
sys.path.append(os.path.join(REPO_DIR, "src"))

import llm
from database import get_connection
from examples import Example, Match, format_sql_examples
from retrieval import EMBEDDING_CACHE_DIR, _normalize, cached_embeddings, ollama_embed
from schema import get_schema

from import_bird_train import DB_PREFIX
from transpile_gold import OUTPUT_PATH as GOLD_PATH

OUT_DIR = os.path.join(FINETUNE_DIR, "data", "sft")
SQL_MODEL = llm.LLMSettings().model
SYSTEM_PROMPT = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
EMBEDDING_MODEL = "bge-m3"
EXAMPLE_COUNTS = (3, 5)  # the few-shot setups measured (3) and the web UI's (APP_SQL_EXAMPLES)
MAX_EXAMPLE_SIMILARITY = 0.9
EMBED_BATCH = 64


def check_system_prompt():
    modelfile = ollama.show(SQL_MODEL).modelfile or ""
    match = re.search(r'^SYSTEM\s+"""(.*?)"""', modelfile, re.S | re.M) or re.search(
        r"^SYSTEM\s+(.+)$", modelfile, re.M)
    found = match.group(1).strip() if match else None
    if found != SYSTEM_PROMPT:
        sys.exit(f"A {SQL_MODEL} system promptja nem a várt: {found!r}")


def batched_embed(model, texts):
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors += ollama_embed(model, texts[start:start + EMBED_BATCH])
    return vectors


def answer_text(sql):
    tree = sqlglot.parse_one(sql, read="postgres")
    pretty = tree.sql(dialect="postgres", pretty=True)
    if sqlglot.parse_one(pretty, read="postgres") != tree:
        raise ValueError(f"pretty print changed the query: {sql}")
    return f"```sql\n{pretty};\n```"


def same_sql(a, b):
    return re.sub(r"\s+", " ", a).strip().lower() == re.sub(r"\s+", " ", b).strip().lower()


def pick_examples(index, items, vectors, n):
    target = items[index]
    scored = []
    for j, other in enumerate(items):
        if j == index or same_sql(other["sql"], target["sql"]):
            continue
        score = sum(a * b for a, b in zip(vectors[index], vectors[j]))
        if score < MAX_EXAMPLE_SIMILARITY:
            scored.append((-score, other["id"], j))
    scored.sort()
    return [(items[j], -neg) for neg, _, j in scored[:n]]


def git_state():
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_DIR).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO_DIR).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def sha256_file(path):
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning tanítóadat (JSONL) a BIRD train ellenőrzött gold SQL-jéből")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--valid-databases", type=int, default=5, help="ennyi teljes adatbázis a validációhoz")
    parser.add_argument("--evidence-share", type=float, default=0.5, help="az evidence-es kérdések ekkora része kapja meg")
    parser.add_argument("--examples-share", type=float, default=0.3, help="a kérdések ekkora része kap few-shot példákat")
    args = parser.parse_args()

    check_system_prompt()
    digest = llm.model_digest(EMBEDDING_MODEL)
    if digest is None:
        sys.exit(f"Hiányzik a beágyazómodell: ollama pull {EMBEDDING_MODEL}")

    with open(GOLD_PATH, encoding="utf-8") as file:
        gold = json.load(file)["questions"]
    by_db = defaultdict(list)
    for item in gold:
        if item["status"] == "ok" and not item.get("empty"):
            by_db[item["db_id"]].append(item)

    rng = random.Random(args.seed)
    databases = sorted(by_db)
    valid_dbs = set(rng.sample(databases, args.valid_databases))

    splits = {"train": [], "valid": []}
    stats = Counter()
    for db_id in databases:
        items = sorted(by_db[db_id], key=lambda x: x["id"])
        conn = get_connection(DB_PREFIX + db_id)
        schema = get_schema(conn, DB_PREFIX + db_id)
        conn.close()
        vectors = [_normalize(v) for v in cached_embeddings(
            batched_embed, EMBEDDING_MODEL, [x["question"] for x in items], EMBEDDING_CACHE_DIR, digest)]
        split = "valid" if db_id in valid_dbs else "train"
        for i, item in enumerate(items):
            evidence = item["evidence"].strip() if item["evidence"] else ""
            show_evidence = bool(evidence) and rng.random() < args.evidence_share
            examples_text, shown = None, []
            if rng.random() < args.examples_share:
                picked = pick_examples(i, items, vectors, rng.choice(EXAMPLE_COUNTS))
                matches = [Match(Example(x["id"], (("en", x["question"]),), x["sql"], ()), x["question"], s)
                           for x, s in picked]
                examples_text = format_sql_examples(matches) or None
                shown = [{"id": x["id"], "score": round(s, 4)} for x, s in picked]
            prompt = llm.sql_prompt(item["question"], schema, examples_text,
                                    evidence if show_evidence else None)
            splits[split].append({
                "id": item["id"],
                "db_id": db_id,
                "evidence_shown": show_evidence,
                "examples": shown,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": answer_text(item["sql"])},
                ],
            })
            stats[f"{split}_evidence"] += show_evidence
            stats[f"{split}_examples"] += bool(shown)
        print(f"{db_id} ({split}): {len(items)} példa")

    os.makedirs(OUT_DIR, exist_ok=True)
    for split, rows in splits.items():
        rng.shuffle(rows)
        with open(os.path.join(OUT_DIR, f"{split}.jsonl"), "w", encoding="utf-8", newline="\n") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")

    lengths = sorted(len(r["messages"][1]["content"]) + len(r["messages"][2]["content"])
                     for rows in splits.values() for r in rows)
    meta = {
        "source": "BIRD train, checked gold SQL (finetune/transpile_gold.py)",
        "settings": vars(args) | {"example_counts": EXAMPLE_COUNTS,
                                  "max_example_similarity": MAX_EXAMPLE_SIMILARITY,
                                  "embedding_model": EMBEDDING_MODEL},
        "sql_model": SQL_MODEL,
        "sql_model_digest": llm.model_digest(SQL_MODEL),
        "embedding_model_digest": digest,
        "system_prompt": SYSTEM_PROMPT,
        "prompt_sha256": llm.PROMPT_SHA256,
        "sql_examples_sha256": llm.SQL_EXAMPLES_SHA256,
        "evidence_sha256": llm.EVIDENCE_SHA256,
        "gold_sha256": sha256_file(GOLD_PATH),
        "git": git_state(),
        "valid_databases": sorted(valid_dbs),
        "counts": {split: len(rows) for split, rows in splits.items()},
        "evidence_shown": {s: stats[f"{s}_evidence"] for s in splits},
        "with_examples": {s: stats[f"{s}_examples"] for s in splits},
        "chars_user_plus_answer": {"median": lengths[len(lengths) // 2], "max": lengths[-1]},
        "files_sha256": {f"{s}.jsonl": sha256_file(os.path.join(OUT_DIR, f"{s}.jsonl")) for s in splits},
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False, indent=1)
    print(json.dumps({k: meta[k] for k in ("valid_databases", "counts", "evidence_shown",
                                           "with_examples", "chars_user_plus_answer")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
