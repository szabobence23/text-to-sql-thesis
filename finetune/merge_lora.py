"""
Merge a trained LoRA adapter (train_lora.py) into the bf16 base model and
save it as a plain Hugging Face model, the input of the GGUF conversion
(export_gguf.sh). With --base-only the base model is saved unchanged: the
conversion control, put through the same conversion and quantization as
the fine-tuned model.

    python merge_lora.py --adapter out/adapter-epoch2 --out merged-ft
    python merge_lora.py --base-only --out merged-base
"""

import argparse
import json
import os

from train_lora import BASE_MODEL


def main():
    parser = argparse.ArgumentParser(description="LoRA merge into the base model")
    parser.add_argument("--adapter", help="adapter folder (adapter-epoch<N>)")
    parser.add_argument("--base-only", action="store_true", help="the base model unchanged (conversion control)")
    parser.add_argument("--base", default=BASE_MODEL)
    parser.add_argument("--meta", help="train_meta.json, for the base model commit (default: next to the adapter)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if bool(args.adapter) == args.base_only:
        parser.error("give either --adapter or --base-only")

    import torch
    from huggingface_hub import HfApi
    from transformers import AutoModelForCausalLM, AutoTokenizer

    meta_path = args.meta or (os.path.join(os.path.dirname(os.path.normpath(args.adapter)), "train_meta.json")
                              if args.adapter else None)
    if meta_path and os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as file:
            commit = json.load(file)["base_commit"]
    else:
        commit = HfApi().model_info(args.base).sha

    # low_cpu_mem_usage: one copy of the weights in RAM, not two (~15 GB
    # instead of ~30 GB; a rented 24 GB-GPU machine may have only ~31 GB).
    model = AutoModelForCausalLM.from_pretrained(args.base, revision=commit, torch_dtype=torch.bfloat16,
                                                 low_cpu_mem_usage=True)
    tokenizer = AutoTokenizer.from_pretrained(args.base, revision=commit)
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
    model.save_pretrained(args.out, safe_serialization=True)
    tokenizer.save_pretrained(args.out)
    with open(os.path.join(args.out, "merge_meta.json"), "w", encoding="utf-8") as file:
        json.dump({"base": args.base, "base_commit": commit, "adapter": args.adapter}, file, indent=1)
    print(f"{args.out}: {'base' if args.base_only else args.adapter} saved (base commit {commit})")


if __name__ == "__main__":
    main()
