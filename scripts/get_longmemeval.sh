#!/usr/bin/env bash
# Download the LongMemEval_S benchmark (external, ~277 MB, not committed).
# Source: huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (Wu et al., 2025).
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/data/longmemeval"
mkdir -p "$DIR"
URL="https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
echo "Downloading LongMemEval_S to $DIR/longmemeval_s.json ..."
curl -sSL -C - "$URL" -o "$DIR/longmemeval_s.json"
echo "Done: $(du -h "$DIR/longmemeval_s.json" | cut -f1)"
