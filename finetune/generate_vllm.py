"""
Candidate answers for self-distillation, on the rented GPU
(docs/finetune.md): the base model's own answers to every prompt of the
SFT data (sft/train.jsonl, sft/valid.jsonl), one greedy and --samples
sampled per prompt, with vLLM. build_self_distill.py checks them at home
on the birdtrain databases and keeps a correct one as the training answer,
so the fine-tuned model learns from answers written in its own style
instead of BIRD's gold SQL.

    python generate_vllm.py --data-dir sft --out distill [--samples 4]

The prompt is the same text train_lora.py trains on (Ollama's template,
checked against the tokenizer's chat template), given as token ids. The
base model is the bf16 Hugging Face model at the commit of the first
training (--revision), the model the adapter is trained on. Sampling uses
the model's own generation_config values (temperature 0.7, top_p 0.8,
top_k 20, repetition_penalty 1.05), set explicitly; greedy has no
repetition penalty, like the pipeline's temperature 0.

Writes --out/generations.jsonl ({id, split, greedy, samples, finish}) and
--out/generate_meta.json (settings, versions, data hashes, seconds).
Needs vLLM in its own venv (requirements-vllm.txt), not next to the
training packages.
"""

import argparse
import hashlib
import json
import os
import time

from train_lora import BASE_MODEL, ollama_prompt, read_jsonl

BASE_COMMIT = "c03e6d358207e414f1eca0bb1891e29f1db0e242"  # the first training's base model (train_meta.json)
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repetition_penalty": 1.05}


def sha256_file(path):
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Self-distillation: the base model's answers to the SFT prompts (vLLM)")
    parser.add_argument("--data-dir", required=True, help="train.jsonl, valid.jsonl")
    parser.add_argument("--out", required=True)
    parser.add_argument("--base", default=BASE_MODEL)
    parser.add_argument("--revision", default=BASE_COMMIT)
    parser.add_argument("--samples", type=int, default=4, help="sampled answers per prompt, next to the greedy one")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, help="only the first N prompts per split (smoke test)")
    args = parser.parse_args()

    import vllm
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    tokenizer = AutoTokenizer.from_pretrained(args.base, revision=args.revision)
    rows, prompts = [], []
    for split in ("train", "valid"):
        for row in read_jsonl(os.path.join(args.data_dir, f"{split}.jsonl"))[:args.limit]:
            prompt = ollama_prompt(row["messages"][:2])
            if prompt != tokenizer.apply_chat_template(row["messages"][:2], tokenize=False, add_generation_prompt=True):
                raise ValueError(f"chat template differs from Ollama's (example {row['id']})")
            rows.append((split, row["id"]))
            prompts.append({"prompt_token_ids": tokenizer(prompt, add_special_tokens=False)["input_ids"]})

    model = LLM(model=args.base, revision=args.revision, tokenizer_revision=args.revision, dtype="bfloat16",
                max_model_len=args.max_model_len, seed=args.seed, generation_config="vllm")
    greedy_params = SamplingParams(temperature=0.0, repetition_penalty=1.0, max_tokens=args.max_tokens)
    sampled_params = SamplingParams(n=args.samples, seed=args.seed, max_tokens=args.max_tokens, **SAMPLING)

    started = time.time()
    greedy = model.generate(prompts, greedy_params)
    greedy_seconds = time.time() - started
    sampled = model.generate(prompts, sampled_params) if args.samples else [None] * len(prompts)
    seconds = time.time() - started

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "generations.jsonl"), "w", encoding="utf-8", newline="\n") as file:
        for (split, row_id), g, s in zip(rows, greedy, sampled):
            outputs = [g.outputs[0]] + (list(s.outputs) if s else [])
            file.write(json.dumps({
                "id": row_id,
                "split": split,
                "greedy": g.outputs[0].text,
                "samples": [o.text for o in s.outputs] if s else [],
                "finish": [o.finish_reason for o in outputs],
            }, ensure_ascii=False) + "\n")

    meta = {
        "base_model": args.base,
        "base_commit": args.revision,
        "settings": vars(args),
        "greedy": {"temperature": 0.0, "repetition_penalty": 1.0},
        "sampling": SAMPLING,
        "vllm": vllm.__version__,
        "data_sha256": {s: sha256_file(os.path.join(args.data_dir, f"{s}.jsonl")) for s in ("train", "valid")},
        "prompts": len(prompts),
        "greedy_seconds": round(greedy_seconds),
        "seconds": round(seconds),
        "generations_sha256": sha256_file(os.path.join(args.out, "generations.jsonl")),
    }
    with open(os.path.join(args.out, "generate_meta.json"), "w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False, indent=1)
    print(f"{len(prompts)} prompts, greedy {meta['greedy_seconds']} s, all {meta['seconds']} s")


if __name__ == "__main__":
    main()
