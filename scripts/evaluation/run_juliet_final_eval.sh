#!/usr/bin/env bash
# Final Juliet LLM evaluation (Ollama): 7 representations × Prompt V2 × 2 models.
# Writes predictions under RESULTS_ROOT/<model_tag>/v2/juliet/
#
# Usage:
#   export OLLAMA_HOST=http://192.168.3.43:11434
#   ./scripts/evaluation/run_juliet_final_eval.sh
#
# Env:
#   OLLAMA_HOST     - Ollama base URL (default http://127.0.0.1:11434)
#   REPO_ROOT       - repo root (default: parent of scripts/evaluation)
#   RESULTS_ROOT    - where to write results (default: $REPO_ROOT/results_inference_juliet_final)
#   INPUT_SUFFIX    - "" = full juliet_article2 files; "_test500" or "_test20" for pilots
#   MODEL_QWEN      - default qwen3.5:35b
#   MODEL_GLM       - default glm-4.7-flash:q8_0

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESULTS_ROOT="${RESULTS_ROOT:-${REPO_ROOT}/results_inference_juliet_final}"
EVAL_DIR="${REPO_ROOT}/datasets/derived/juliet_article2"
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
INPUT_SUFFIX="${INPUT_SUFFIX:-}"
MODEL_QWEN="${MODEL_QWEN:-qwen3.5:35b}"
MODEL_GLM="${MODEL_GLM:-glm-4.7-flash:q8_0}"

REPS="rawcode,ast,cfg,dfg,cpg,slice,llm_summary"
PROMPT_PROFILE="detector_prompt_v2_risk_first"

run_one() {
  local model="$1"
  local tag="$2"
  local out="${RESULTS_ROOT}/${tag}/v2"
  mkdir -p "${out}"
  python3 "${REPO_ROOT}/scripts/evaluation/run_inference_all.py" \
    --model "${model}" \
    --host "${HOST}" \
    --eval-dir "${EVAL_DIR}" \
    --results-dir "${out}" \
    --datasets juliet \
    --representations "${REPS}" \
    --prompt-profile "${PROMPT_PROFILE}" \
    --input-suffix "${INPUT_SUFFIX}" \
    --num-predict 64 \
    --temperature 0 \
    --timeout-s 300
}

echo "REPO_ROOT=${REPO_ROOT}"
echo "EVAL_DIR=${EVAL_DIR}"
echo "RESULTS_ROOT=${RESULTS_ROOT}"
echo "INPUT_SUFFIX='${INPUT_SUFFIX}' (empty = full juliet_article2 *_for_llm_juliet.jsonl)"
echo "HOST=${HOST}"
echo "PROMPT=V2_only (${PROMPT_PROFILE})"

run_one "${MODEL_QWEN}" "qwen35"
run_one "${MODEL_GLM}" "glm47"

echo "Done. Predictions: ${RESULTS_ROOT}/<qwen35|glm47>/v2/juliet/*_predictions.jsonl"
