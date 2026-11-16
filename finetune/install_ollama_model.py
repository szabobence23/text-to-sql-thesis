"""
Load a GGUF made by export_gguf.sh into the local Ollama with the Modelfile
of qwen2.5-coder:7b (template, system prompt, parameters, license) and only
the FROM line changed, so the weights are the only difference from the
base model. Checks afterwards that template and system prompt are the
same, and prints the new model's digest (recorded by the evaluator).

    python finetune/install_ollama_model.py <gguf> <name> [--base qwen2.5-coder:7b]
    python finetune/install_ollama_model.py export/qwen2.5-coder-7b-ft-q4_k_m.gguf qwen2.5-coder-7b-ft
    python finetune/install_ollama_model.py export/qwen2.5-coder-7b-base-q4_k_m.gguf qwen2.5-coder-7b-base-conv

Then measure with the evaluator's --model <name>.
"""

import argparse
import os
import re
import subprocess
import sys

FINETUNE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(FINETUNE_DIR), "src"))

from llm import model_digest

MODELFILE_DIR = os.path.join(FINETUNE_DIR, "data", "ollama")


def ollama(*args):
    result = subprocess.run(["ollama", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"ollama {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="GGUF betöltése Ollamába a base modell Modelfile-jával")
    parser.add_argument("gguf")
    parser.add_argument("name", help="az új Ollama modell neve, pl. qwen2.5-coder-7b-ft")
    parser.add_argument("--base", default="qwen2.5-coder:7b")
    args = parser.parse_args()

    gguf = os.path.abspath(args.gguf)
    if not os.path.exists(gguf):
        sys.exit(f"Nincs ilyen fájl: {gguf}")

    base_modelfile = ollama("show", args.base, "--modelfile")
    lines = base_modelfile.splitlines()
    from_lines = [i for i, line in enumerate(lines) if re.match(r"^FROM\s", line)]
    if len(from_lines) != 1:
        sys.exit(f"A {args.base} Modelfile-jában {len(from_lines)} FROM sor van, 1 kellene")
    lines[from_lines[0]] = f"FROM {gguf}"
    os.makedirs(MODELFILE_DIR, exist_ok=True)
    path = os.path.join(MODELFILE_DIR, f"{args.name}.Modelfile")
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines) + "\n")

    print(f"{args.name} létrehozása ({path})...")
    ollama("create", args.name, "-f", path)

    for what in ("--template", "--system"):
        if ollama("show", args.name, what) != ollama("show", args.base, what):
            sys.exit(f"{args.name}: a {what} nem egyezik a {args.base} modellével")
    print(f"{args.name} kész: template és system prompt = {args.base}, digest {model_digest(args.name)}")


if __name__ == "__main__":
    main()
