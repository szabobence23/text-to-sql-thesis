"""
Self-distilled fine-tuning data (the second fine-tuning, docs/finetune.md):
the base model's own answers to the SFT prompts (generate_vllm.py on the
rented GPU) are checked on the birdtrain databases, and a correct one
becomes the training answer instead of BIRD's gold SQL. Builds two data
sets on the same questions, so the comparison changes one thing at a time:

- sft_self: the model's own correct answer (style of the base model);
- sft_goldsub: the gold answer of sft/ (BIRD style), for exactly the same
  questions, prompts and order: the control for "fewer, easier questions".

    python finetune/build_self_distill.py <distill folder with generations.jsonl>

Candidates per question, in this order: the greedy answer, then the
sampled ones; the first correct one is kept (identical SQL texts are run
once). Correct = it passes validate_sql, runs as the read-only role, and
its rows match the gold answer's by set EX (BIRD's metric) or relaxed EX
(the own test sets' metric: every gold column present, extra columns
allowed), so a correct answer with an extra descriptive column, the base
model's habit, is not thrown away. Questions with no correct candidate are
left out of both sets.

The training answer is the model's own text: its ```sql block as written
(the response itself when it is nothing else, which is the usual case).

Writes finetune/data/sft_self/ and finetune/data/sft_goldsub/ (train.jsonl,
valid.jsonl, meta.json) and finetune/data/distill/check.json (per question:
which candidate was kept, the outcome of every candidate checked).
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(FINETUNE_DIR)
sys.path.append(os.path.join(REPO_DIR, "src"))

import llm
from database import execute_query, get_connection
from evaluation.comparison import is_order_sensitive, normalize_rows, relaxed_match, set_match
from sql_validator import validate_sql

from build_sft_data import git_state, sha256_file
from import_bird_train import DB_PREFIX

DATA_DIR = os.path.join(FINETUNE_DIR, "data")
SFT_DIR = os.path.join(DATA_DIR, "sft")
_FENCE = re.compile(r"```(?:sql)?[ \t]*\n(.*?)```", re.S | re.I)


def answer_from_response(text):
    """The training answer made of a model response: the response itself if
    it is a single ```sql block, else the first code block (or the whole
    text) put in one; None if there is no SQL."""
    stripped = text.strip()
    blocks = _FENCE.findall(stripped)
    if len(blocks) == 1 and stripped.startswith("```sql\n") and stripped.endswith("```"):
        return stripped
    sql = llm.extract_sql(stripped)
    return f"```sql\n{sql}\n```" if sql else None


def candidates(generation):
    """[(source, response)] in checking order, identical SQL once."""
    seen, out = set(), []
    for source, text in [("greedy", generation["greedy"])] + [
            (f"sample{i}", t) for i, t in enumerate(generation["samples"])]:
        key = re.sub(r"\s+", " ", llm.extract_sql(text)).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append((source, text))
    return out


def check(conn, sql, expected, ordered):
    """Outcome of one candidate: 'set', 'relaxed', 'wrong', 'error' or 'invalid'."""
    try:
        valid, _ = validate_sql(conn, sql)
    except Exception:  # a validator crash counts as an invalid query, never as a correct one
        valid = False
    if not valid:
        return "invalid"
    try:
        rows = normalize_rows(execute_query(conn, sql))
    except Exception:  # execution error (Postgres), as the evaluator counts it
        return "error"
    if set_match(expected, rows):
        return "set"
    if relaxed_match(expected, rows, ordered):
        return "relaxed"
    return "wrong"


def choose(generation, judge):
    """(kept source, kept response, [(source, outcome)]) with judge(sql) ->
    outcome; the first 'set' or 'relaxed' candidate is kept."""
    tried = []
    for source, text in candidates(generation):
        outcome = judge(llm.extract_sql(text))
        tried.append((source, outcome))
        if outcome in ("set", "relaxed"):
            return source, text, tried
    return None, None, tried


def read_jsonl(path):
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def write_set(name, rows, meta):
    out_dir = os.path.join(DATA_DIR, name)
    os.makedirs(out_dir, exist_ok=True)
    for split in ("train", "valid"):
        with open(os.path.join(out_dir, f"{split}.jsonl"), "w", encoding="utf-8", newline="\n") as file:
            for row in rows[split]:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = meta | {
        "counts": {s: len(rows[s]) for s in rows},
        "evidence_shown": {s: sum(r["evidence_shown"] for r in rows[s]) for s in rows},
        "with_examples": {s: sum(bool(r["examples"]) for r in rows[s]) for s in rows},
        "files_sha256": {f"{s}.jsonl": sha256_file(os.path.join(out_dir, f"{s}.jsonl")) for s in rows},
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False, indent=1)
    return meta


def main():
    parser = argparse.ArgumentParser(description="Önmagán tanítás: a modell helyes saját válaszaiból tanítóadat")
    parser.add_argument("distill_dir", help="generations.jsonl és generate_meta.json mappája")
    parser.add_argument("--limit", type=int, help="csak az első N kérdés splitenként (próbához)")
    args = parser.parse_args()

    generations = {(g["split"], g["id"]): g for g in read_jsonl(os.path.join(args.distill_dir, "generations.jsonl"))}
    with open(os.path.join(args.distill_dir, "generate_meta.json"), encoding="utf-8") as file:
        generate_meta = json.load(file)
    with open(os.path.join(SFT_DIR, "meta.json"), encoding="utf-8") as file:
        sft_meta = json.load(file)
    for split in ("train", "valid"):
        if generate_meta["data_sha256"][split] != sft_meta["files_sha256"][f"{split}.jsonl"]:
            sys.exit(f"A generálás nem a mostani sft/{split}.jsonl-re készült")

    connections, checked, stats = {}, [], Counter()
    rows = {"self": {"train": [], "valid": []}, "goldsub": {"train": [], "valid": []}}
    try:
        for split in ("train", "valid"):
            examples = read_jsonl(os.path.join(SFT_DIR, f"{split}.jsonl"))[:args.limit]
            for index, example in enumerate(examples, start=1):
                db = example["db_id"]
                if db not in connections:
                    connections[db] = get_connection(DB_PREFIX + db)
                conn = connections[db]
                gold_sql = llm.extract_sql(example["messages"][2]["content"])
                expected = normalize_rows(execute_query(conn, gold_sql))
                ordered = is_order_sensitive(gold_sql)
                source, text, tried = choose(generations[(split, example["id"])],
                                             lambda sql: check(conn, sql, expected, ordered))
                answer = answer_from_response(text) if text else None
                checked.append({"split": split, "id": example["id"], "db_id": db,
                                "kept": source if answer else None, "tried": tried})
                stats[f"{split}_{source or 'none'}"] += 1
                if answer:
                    stats[f"{split}_{dict(tried)[source]}"] += 1
                    keep = {k: example[k] for k in ("id", "db_id", "evidence_shown", "examples")}
                    rows["goldsub"][split].append(keep | {"messages": example["messages"]})
                    rows["self"][split].append(keep | {"messages": example["messages"][:2] + [
                        {"role": "assistant", "content": answer}]})
                if index % 250 == 0 or index == len(examples):
                    print(f"{split} {index}/{len(examples)}: {len(rows['self'][split])} megtartva", flush=True)
    finally:
        for conn in connections.values():
            conn.close()

    os.makedirs(os.path.join(DATA_DIR, "distill"), exist_ok=True)
    check_path = os.path.join(DATA_DIR, "distill", "check.json")
    with open(check_path, "w", encoding="utf-8") as file:
        json.dump({"stats": dict(stats), "questions": checked}, file, ensure_ascii=False, indent=1)

    common = {
        "generations_sha256": sha256_file(os.path.join(args.distill_dir, "generations.jsonl")),
        "generate_meta": generate_meta,
        "sft_meta": sft_meta,
        "check_sha256": sha256_file(check_path),
        "kept_by": {k: v for k, v in sorted(stats.items())},
        "criterion": "validate_sql, runs as the reader role, set EX or relaxed EX against the gold answer",
        "limit": args.limit,
        "git": git_state(),
        "system_prompt": sft_meta["system_prompt"],
        "prompt_sha256": llm.PROMPT_SHA256,
    }
    for name, source in (("sft_self", "the base model's own correct answer (self-distillation)"),
                         ("sft_goldsub", "BIRD gold answer of sft/, same questions as sft_self")):
        meta = write_set(name, rows[name.removeprefix("sft_")], common | {"source": source})
        print(f"{name}: {meta['counts']}, evidence {meta['evidence_shown']}, examples {meta['with_examples']}")
    print(json.dumps(common["kept_by"], indent=1))


if __name__ == "__main__":
    main()
