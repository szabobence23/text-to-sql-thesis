#!/usr/bin/env bash
# Fine-tuned model -> Q4_K_M GGUF for Ollama, on the rented GPU machine
# (docs/finetune.md). Also puts the unchanged base model through the same
# merge, conversion and quantization: the conversion control, so a
# difference between the fine-tuned model and the Ollama library model
# can be told apart from what the conversion itself changes.
#
#   bash export_gguf.sh <adapter folder> <output folder>
#   bash export_gguf.sh out/adapter-epoch2 export
#   NAME=ft-self BASE=0 bash export_gguf.sh out-self/adapter-epoch1 export-self
#
# NAME names the fine-tuned file (default ft). BASE=0 skips the base model,
# when its conversion control was already exported with the same llama.cpp
# commit (LLAMA_COMMIT, default the one of the first export).
# Needs ~80 GB of disk (two merged bf16 models, one f16 GGUF at a time).
# Output: qwen2.5-coder-7b-<NAME>-q4_k_m.gguf, qwen2.5-coder-7b-base-q4_k_m.gguf,
# export_meta.json (llama.cpp commit, sha256 of the files).
set -euo pipefail

ADAPTER=$1
OUT=$2
NAME=${NAME:-ft}
BASE=${BASE:-1}
LLAMA_COMMIT=${LLAMA_COMMIT:-e574a17b062be51b98e239ccd3d3743e3d902333}
WORK=${WORK:-/workspace}
LLAMA=$WORK/llama.cpp
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
NAMES=$NAME
if [ "$BASE" = 1 ]; then NAMES="$NAME base"; fi

python "$HERE/merge_lora.py" --adapter "$ADAPTER" --out "$WORK/merged-$NAME"
if [ "$BASE" = 1 ]; then
    python "$HERE/merge_lora.py" --base-only --meta "$(dirname "$ADAPTER")/train_meta.json" --out "$WORK/merged-base"
fi

# llama.cpp's converter in its own venv, so its requirements do not change
# the training packages.
command -v cmake > /dev/null || (apt-get update -qq && apt-get install -y -qq cmake build-essential > /dev/null)
[ -d "$LLAMA" ] || git clone https://github.com/ggml-org/llama.cpp "$LLAMA"
git -C "$LLAMA" checkout -q "$LLAMA_COMMIT"
[ -d "$WORK/venv-gguf" ] || python -m venv "$WORK/venv-gguf"
"$WORK/venv-gguf/bin/pip" install -q -r "$LLAMA/requirements/requirements-convert_hf_to_gguf.txt"
cmake -S "$LLAMA" -B "$LLAMA/build" -DGGML_CUDA=OFF -DLLAMA_CURL=OFF > /dev/null
cmake --build "$LLAMA/build" --target llama-quantize -j > /dev/null

for N in $NAMES; do
    "$WORK/venv-gguf/bin/python" "$LLAMA/convert_hf_to_gguf.py" "$WORK/merged-$N" \
        --outtype f16 --outfile "$WORK/$N-f16.gguf"
    "$LLAMA/build/bin/llama-quantize" "$WORK/$N-f16.gguf" "$OUT/qwen2.5-coder-7b-$N-q4_k_m.gguf" Q4_K_M
    rm -- "${WORK:?}/${N:?}-f16.gguf"
done

{
    echo "{"
    echo "  \"adapter\": \"$ADAPTER\","
    echo "  \"llama_cpp_commit\": \"$(git -C "$LLAMA" rev-parse HEAD)\","
    echo "  \"quantization\": \"Q4_K_M\","
    for N in $NAMES; do
        echo "  \"${N}_sha256\": \"$(sha256sum "$OUT/qwen2.5-coder-7b-$N-q4_k_m.gguf" | cut -d' ' -f1)\","
    done
    echo "  \"name\": \"$NAME\""
    echo "}"
} > "$OUT/export_meta.json"
cp "$(dirname "$ADAPTER")/train_meta.json" "$OUT/"
ls -lh "$OUT"
