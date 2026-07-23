#!/usr/bin/env bash
# Download the LongMemEval_S benchmark (external, ~277 MB, not committed).
# Source: huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (Wu et al., 2025).
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)/data/longmemeval"
mkdir -p "$DIR"
URL="https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
TARGET="$DIR/longmemeval_s.json"
PARTIAL="$DIR/longmemeval_s.json.partial"
echo "Downloading LongMemEval_S to $TARGET ..."
# Continue an interrupted transfer, retry transient failures, and keep a
# partial file separate from the validated target so consumers never ingest a
# truncated JSON document.
curl --fail --show-error --location --retry 5 --retry-delay 2 --retry-connrefused \
  --continue-at - "$URL" -o "$PARTIAL"
uv run --project "$(cd "$(dirname "$0")/.." && pwd)" python - "$PARTIAL" <<'PY'
import hashlib
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
from src.evaluation.longmemeval import validate_longmemeval_payload

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_longmemeval_payload(payload)
except Exception as exc:
    raise SystemExit(f"LongMemEval download is partial or invalid: {type(exc).__name__}: {exc}")
digest = hashlib.sha256(path.read_bytes()).hexdigest()
print(f"validated records={len(payload)} bytes={path.stat().st_size} sha256={digest}")
PY
mv "$PARTIAL" "$TARGET"
echo "Done: $(du -h "$TARGET" | cut -f1)"
