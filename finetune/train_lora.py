"""
LoRA fine-tuning of Qwen2.5-Coder-7B-Instruct on the data of
build_sft_data.py (finetune/data/sft). Runs on a rented GPU (an RTX 4090
with 24 GB is enough), not on the laptop: docs/finetune.md has the steps.

    python train_lora.py --data-dir sft --out-dir out [--epochs 2] [--lr 1e-4]
    python train_lora.py --data-dir sft --out-dir out --dry-run   # tokenize and check only

bf16 LoRA, not QLoRA: the adapter is learned on the same weights it is
merged into (merge_lora.py), so the merged model is the one that was
trained. --load-in-4bit (QLoRA) is only a fallback if memory runs out.

Every example is rendered with the tokenizer's chat template and its prompt
part is checked to be byte for byte what Ollama's template for
qwen2.5-coder:7b sends (ollama_prompt below), so the model is trained on
what it will see. The loss is on the assistant turn only: the ```sql block
and the <|im_end|> that ends it.

Writes to --out-dir: adapter-epoch<N>/ after every epoch and
train_meta.json (settings, package versions, base model commit, data
hashes, train / validation loss per epoch, times).
"""

import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
IGNORE = -100


def ollama_prompt(messages):
    """
    The text Ollama's template for qwen2.5-coder:7b (ollama show --template)
    makes of a system + user conversation, ending with the assistant header.
    """
    system, user = messages
    assert system["role"] == "system" and user["role"] == "user"
    return (f"<|im_start|>system\n{system['content']}<|im_end|>\n"
            f"<|im_start|>user\n{user['content']}<|im_end|>\n"
            f"<|im_start|>assistant\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def sha256_file(path):
    with open(path, "rb") as file:
        return hashlib.sha256(file.read()).hexdigest()


def encode(tokenizer, row, max_len):
    """input_ids and labels (prompt masked) of one chat, or None if too long."""
    messages = row["messages"]
    prompt = tokenizer.apply_chat_template(messages[:2], tokenize=False, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(messages, tokenize=False)
    if prompt != ollama_prompt(messages[:2]):
        raise ValueError(f"chat template differs from Ollama's (example {row['id']})")
    if not full.startswith(prompt):
        raise ValueError(f"the full chat does not start with the prompt (example {row['id']})")
    answer = full[len(prompt):]
    if not answer.startswith(messages[2]["content"] + "<|im_end|>"):
        raise ValueError(f"unexpected assistant turn (example {row['id']}): {answer[-40:]!r}")
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
    ids = prompt_ids + answer_ids
    if len(ids) > max_len:
        return None
    return {"input_ids": ids, "attention_mask": [1] * len(ids),
            "labels": [IGNORE] * len(prompt_ids) + answer_ids}


def encode_all(tokenizer, rows, max_len):
    encoded, too_long = [], 0
    for row in rows:
        item = encode(tokenizer, row, max_len)
        if item is None:
            too_long += 1
        else:
            encoded.append(item)
    return encoded, too_long


def pip_freeze():
    result = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
    return result.stdout.splitlines()


def main():
    parser = argparse.ArgumentParser(description="LoRA fine-tuning (Qwen2.5-Coder-7B-Instruct)")
    parser.add_argument("--data-dir", required=True, help="train.jsonl, valid.jsonl, meta.json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base", default=BASE_MODEL)
    parser.add_argument("--revision", default="main", help="the base model's Hugging Face revision")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=1, help="per step; no padding at 1")
    parser.add_argument("--grad-accum", type=int, default=16, help="effective batch = batch-size * grad-accum")
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--max-len", type=int, default=3072)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--load-in-4bit", action="store_true", help="QLoRA, only if bf16 runs out of memory")
    parser.add_argument("--limit", type=int, help="only this many examples (smoke test)")
    parser.add_argument("--max-steps", type=int, default=-1, help="stop after this many steps (smoke test)")
    parser.add_argument("--dry-run", action="store_true", help="tokenize and check only, no model")
    args = parser.parse_args()

    from huggingface_hub import HfApi
    from transformers import AutoTokenizer

    os.makedirs(args.out_dir, exist_ok=True)
    random.seed(args.seed)
    commit = HfApi().model_info(args.base, revision=args.revision).sha
    tokenizer = AutoTokenizer.from_pretrained(args.base, revision=commit)

    data = {}
    for split in ("train", "valid"):
        rows = read_jsonl(os.path.join(args.data_dir, f"{split}.jsonl"))
        if args.limit:
            rows = rows[:args.limit]
        data[split], too_long = encode_all(tokenizer, rows, args.max_len)
        tokens = sum(len(x["input_ids"]) for x in data[split])
        target = sum(sum(1 for t in x["labels"] if t != IGNORE) for x in data[split])
        print(f"{split}: {len(data[split])} examples ({too_long} longer than {args.max_len} tokens left out), "
              f"{tokens} tokens, {target} of them trained on")

    meta = {
        "base_model": args.base,
        "base_commit": commit,
        "settings": vars(args),
        "data_meta": json.load(open(os.path.join(args.data_dir, "meta.json"), encoding="utf-8")),
        "data_sha256": {s: sha256_file(os.path.join(args.data_dir, f"{s}.jsonl")) for s in ("train", "valid")},
        "examples": {s: len(v) for s, v in data.items()},
        "tokens": {s: sum(len(x["input_ids"]) for x in v) for s, v in data.items()},
        "max_tokens": max(len(x["input_ids"]) for v in data.values() for x in v),
        "python": platform.python_version(),
    }
    if args.dry_run:
        print(json.dumps({k: meta[k] for k in ("base_commit", "examples", "tokens", "max_tokens")}, indent=1))
        return

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, BitsAndBytesConfig, DataCollatorForSeq2Seq,
                              Trainer, TrainerCallback, TrainingArguments)

    torch.manual_seed(args.seed)
    bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float32
    quantization = None
    if args.load_in_4bit:
        quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                          bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, revision=commit, torch_dtype=dtype, quantization_config=quantization,
        attn_implementation="sdpa", device_map={"": 0} if torch.cuda.is_available() else None,
    )
    model.config.use_cache = False
    if args.load_in_4bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    else:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        target_modules=LORA_TARGETS, bias="none", task_type="CAUSAL_LM",
    ))
    model.print_trainable_parameters()

    class SaveEachEpoch(TrainerCallback):
        def on_epoch_end(self, train_args, state, control, **kwargs):
            epoch = round(state.epoch)
            model.save_pretrained(os.path.join(args.out_dir, f"adapter-epoch{epoch}"))
            print(f"adapter-epoch{epoch} saved")

    steps_per_epoch = math.ceil(len(data["train"]) / (args.batch_size * args.grad_accum))
    training_args = TrainingArguments(
        output_dir=os.path.join(args.out_dir, "trainer"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        weight_decay=0.0,
        bf16=bf16,
        logging_steps=max(1, steps_per_epoch // 20),
        eval_strategy="epoch",
        save_strategy="no",
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        group_by_length=args.batch_size > 1,
        remove_unused_columns=False,
        optim="paged_adamw_8bit" if args.load_in_4bit else "adamw_torch",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=data["train"],
        eval_dataset=data["valid"],
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=IGNORE),
        callbacks=[SaveEachEpoch()],
    )
    started = time.time()
    trainer.train()
    meta["train_seconds"] = round(time.time() - started)
    meta["log_history"] = trainer.state.log_history
    meta["eval_loss_per_epoch"] = {round(e["epoch"]): e["eval_loss"]
                                   for e in trainer.state.log_history if "eval_loss" in e}
    meta["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    meta["peak_gpu_memory_gb"] = (round(torch.cuda.max_memory_allocated() / 1e9, 1)
                                  if torch.cuda.is_available() else None)
    meta["torch"] = torch.__version__
    meta["pip_freeze"] = pip_freeze()
    if args.max_steps > 0:
        model.save_pretrained(os.path.join(args.out_dir, "adapter-final"))
    with open(os.path.join(args.out_dir, "train_meta.json"), "w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False, indent=1)
    print("validation loss per epoch:", meta["eval_loss_per_epoch"])
    print(f"done in {meta['train_seconds']} s, peak GPU memory {meta['peak_gpu_memory_gb']} GB")


if __name__ == "__main__":
    main()
