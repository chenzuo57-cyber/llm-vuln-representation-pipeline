#!/usr/bin/env bash
set -euo pipefail
# End-to-end: JSONL -> snippet dir -> joern (import + dump) -> merged JSONL with ast_joern_text.
# Requires: joern on PATH, Java 11+, and a Joern release (https://github.com/joernio/joern/releases).
#
# Usage:
#   ./scripts/representations/run_joern_ast.sh \
#     datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
#     datasets/derived/primevul_test_article2/joern_ast.jsonl

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INPUT="${1:?usage: $0 INPUT.jsonl OUTPUT.jsonl [LIMIT]}"
OUTPUT="${2:?}"
LIMIT="${3:-0}"

WORKDIR="${ROOT}/work/joern_ast_$(date +%s)_$$"
SNIP="${WORKDIR}/snippets"
AST="${WORKDIR}/ast_out"
mkdir -p "${SNIP}" "${AST}"

if ! command -v joern >/dev/null 2>&1; then
  echo "error: 'joern' not found on PATH. Install Joern CLI and retry." >&2
  exit 1
fi

# Prefer local JDK 17 for Joern frontends (required by recent c2cpg builds).
if [[ -x "$HOME/.local/java/jdk-17/bin/java" ]]; then
  export JAVA_HOME="$HOME/.local/java/jdk-17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

PY=(python3)
if [[ "${LIMIT}" != "0" && -n "${LIMIT}" ]]; then
  "${PY[@]}" "${ROOT}/scripts/representations/prepare_joern_snippet_dir.py" --input "${INPUT}" --out-dir "${SNIP}" --limit "${LIMIT}"
else
  "${PY[@]}" "${ROOT}/scripts/representations/prepare_joern_snippet_dir.py" --input "${INPUT}" --out-dir "${SNIP}"
fi

export JOERN_SNIPPET_DIR="$(realpath "${SNIP}")"
export JOERN_AST_OUT="$(realpath "${AST}")"

joern --script "${ROOT}/scripts/representations/joern_dump_ast.sc"

"${PY[@]}" "${ROOT}/scripts/representations/merge_joern_ast_to_jsonl.py" \
  --input "${INPUT}" \
  --manifest "${SNIP}/manifest.json" \
  --ast-dir "${AST}" \
  --output "${OUTPUT}"

echo "Done: ${OUTPUT}"
echo "Intermediate: ${WORKDIR}"
