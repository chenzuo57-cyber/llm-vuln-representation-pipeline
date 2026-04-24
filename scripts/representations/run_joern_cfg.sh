#!/usr/bin/env bash
set -euo pipefail
# End-to-end: JSONL -> snippet dir -> joern (import + cfg dump) -> merged JSONL with cfg_joern_text.
# Usage:
#   ./scripts/representations/run_joern_cfg.sh INPUT.jsonl OUTPUT.jsonl [LIMIT]

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INPUT="${1:?usage: $0 INPUT.jsonl OUTPUT.jsonl [LIMIT]}"
OUTPUT="${2:?}"
LIMIT="${3:-0}"

WORKDIR="${ROOT}/work/joern_cfg_$(date +%s)_$$"
SNIP="${WORKDIR}/snippets"
CFG="${WORKDIR}/cfg_out"
mkdir -p "${SNIP}" "${CFG}"

if ! command -v joern >/dev/null 2>&1; then
  echo "error: 'joern' not found on PATH. Install Joern CLI and retry." >&2
  exit 1
fi

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
export JOERN_CFG_OUT="$(realpath "${CFG}")"

joern --script "${ROOT}/scripts/representations/joern_dump_cfg.sc"

"${PY[@]}" "${ROOT}/scripts/representations/merge_joern_cfg_to_jsonl.py" \
  --input "${INPUT}" \
  --manifest "${SNIP}/manifest.json" \
  --cfg-dir "${CFG}" \
  --output "${OUTPUT}"

echo "Done: ${OUTPUT}"
echo "Intermediate: ${WORKDIR}"
