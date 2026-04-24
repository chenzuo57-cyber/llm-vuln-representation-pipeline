# Phd-A2: Reproducible Vulnerability Representation Pipeline

This repository provides an end-to-end pipeline to reproduce vulnerability-detection experiments across multiple code representations and LLM backends.

## Scope

- Datasets:
  - PrimeVul (primary)
  - Juliet v1.3 C/C++ (secondary)
- Representations:
  - `rawcode`, `ast`, `cfg`, `dfg`, `cpg`, `slice`, `llm_summary`
- Evaluation:
  - Prompt V2 (`detector_prompt_v2_risk_first`) is the default/primary protocol.
  - V1 is legacy and disabled by default in `run_inference_all.py`.

## Repository Layout

- `scripts/datasets/`: dataset download + normalization + filtering
- `scripts/representations/`: Joern extraction and conversion to text-based JSONL
- `scripts/evaluation/`: inference runners (single/full runs)
- `configs/`: dataset subset configs (CWE allowlists)
- `results/`: compact merged outputs/metrics intended for sharing
- `datasets/`: generated data artifacts (typically large; usually ignored in git)
- `work/`, `workspace/`: transient Joern/runtime artifacts

## Folder and File Structure Guide

This section shows the practical structure to keep for a reusable public repo.

```text
Phd-A2/
├── README.md
├── requirements.txt
├── .gitignore
├── configs/
│   ├── article2_juliet_cwe_subset.v1.json
│   └── article2_primevul_cwe_subset.v1.json
├── scripts/
│   ├── datasets/
│   │   ├── download_primevul.py
│   │   ├── download_juliet.py
│   │   ├── prepare_primevul.py
│   │   ├── prepare_juliet.py
│   │   └── filter_normalized_jsonl.py
│   ├── representations/
│   │   ├── run_joern_ast.sh
│   │   ├── run_joern_cfg.sh
│   │   ├── run_joern_dfg.sh
│   │   ├── run_joern_cpg.sh
│   │   ├── run_joern_slice.sh
│   │   ├── joern_dump_ast.sc
│   │   ├── joern_dump_cfg.sc
│   │   ├── joern_dump_dfg.sc
│   │   ├── joern_dump_cpg.sc
│   │   ├── joern_dump_slice.sc
│   │   ├── merge_joern_ast_to_jsonl.py
│   │   ├── merge_joern_cfg_to_jsonl.py
│   │   ├── merge_joern_dfg_to_jsonl.py
│   │   ├── merge_joern_cpg_to_jsonl.py
│   │   ├── merge_joern_slice_to_jsonl.py
│   │   ├── prepare_joern_snippet_dir.py
│   │   ├── extract_code_for_llm.py
│   │   ├── extract_representation_for_llm.py
│   │   └── generate_llm_summary_ollama.py
│   └── evaluation/
│       ├── run_inference_all.py
│       ├── run_juliet_final_eval.sh
│       ├── run_primevul_final_eval.sh
│       └── run_juliet_final_eval.sh
├── results/
│   ├── juliet/
│   └── primevul/
└── datasets/   (generated locally, usually not committed)
```

### Must-Keep Core Representation Files

Do not delete these if you want users to rebuild representations from scratch:

- `run_joern_*.sh` (pipeline orchestration)
- `joern_dump_*.sc` (Joern graph dump logic)
- `merge_joern_*_to_jsonl.py` (map Joern outputs back to dataset rows)

## Requirements

- Linux/macOS shell environment
- Python 3.10+ recommended
- Java 11+ (Java 17 recommended for recent Joern frontends)
- Joern CLI on `PATH`
- Ollama server (local or remote)

Install Python deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 1) Download and Prepare Datasets

Download raw datasets:

```bash
python3 scripts/datasets/download_primevul.py
python3 scripts/datasets/download_juliet.py
```

Normalize:

```bash
python3 scripts/datasets/prepare_primevul.py
python3 scripts/datasets/prepare_juliet.py
```

Create Article2 subsets using CWE allowlists:

```bash
python3 scripts/datasets/filter_normalized_jsonl.py \
  --input datasets/juliet/prepared/juliet_normalized.jsonl \
  --output datasets/juliet/prepared/juliet_article2_subset.jsonl \
  --cwe-config configs/article2_juliet_cwe_subset.v1.json

python3 scripts/datasets/filter_normalized_jsonl.py \
  --input datasets/primevul/prepared/primevul_test_normalized.jsonl \
  --output datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  --cwe-config configs/article2_primevul_cwe_subset.v1.json
```

## 2) Build Joern-Based Representations

Install Joern from [joern releases](https://github.com/joernio/joern/releases), then ensure:

```bash
joern --version
```

Example (PrimeVul test subset):

```bash
./scripts/representations/run_joern_ast.sh \
  datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  datasets/derived/primevul_test_article2/joern_ast.jsonl

./scripts/representations/run_joern_cfg.sh \
  datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  datasets/derived/primevul_test_article2/joern_cfg.jsonl

./scripts/representations/run_joern_dfg.sh \
  datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  datasets/derived/primevul_test_article2/joern_dfg.jsonl

./scripts/representations/run_joern_cpg.sh \
  datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  datasets/derived/primevul_test_article2/joern_cpg.jsonl

./scripts/representations/run_joern_slice.sh \
  datasets/primevul/prepared/primevul_test_article2_subset.jsonl \
  datasets/derived/primevul_test_article2/joern_slice.jsonl
```

Each runner supports an optional `LIMIT` as the 3rd argument for smoke tests.

## 3) Convert to LLM Text Inputs

Use:

- `scripts/representations/extract_code_for_llm.py`
- `scripts/representations/extract_representation_for_llm.py`
- `scripts/representations/generate_llm_summary_ollama.py` (optional summaries)

Expected output naming convention:

- `<rep>_for_llm_<dataset>.jsonl`
- Example: `ast_for_llm_juliet.jsonl`

## 4) Ollama Connection (Local or Remote)

All evaluation scripts use Ollama HTTP `/api/generate`.

- Local default: `http://127.0.0.1:11434`
- Remote example: `http://192.168.3.43:11434`

Quick connectivity check:

```bash
curl -s http://127.0.0.1:11434/api/tags
```

Or remote:

```bash
curl -s http://192.168.3.43:11434/api/tags
```

Set once per session:

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
```

## 5) Run Evaluations

### Single-run inference (generic)

```bash
python3 scripts/evaluation/run_inference_all.py \
  --model qwen3.5:35b \
  --host "$OLLAMA_HOST" \
  --eval-dir datasets/derived/juliet_article2 \
  --results-dir results_inference_example \
  --datasets juliet \
  --representations rawcode,ast,cfg,dfg,cpg,slice,llm_summary \
  --prompt-profile detector_prompt_v2_risk_first
```

### Juliet final (V2, both models, all 7 reps)

```bash
./scripts/evaluation/run_juliet_final_eval.sh
```

### Juliet full run (V2, both models, all 7 reps)

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
./scripts/evaluation/run_juliet_final_eval.sh
```

### PrimeVul final (V2, both models, all 7 reps)

```bash
./scripts/evaluation/run_primevul_final_eval.sh
```

## Prompt Policy

- Primary prompt: `detector_prompt_v2_risk_first`
- V1 is blocked by default in `run_inference_all.py`
- To run legacy V1 explicitly:

```bash
export ALLOW_DEPRECATED_V1_PROMPT=1
```

## Reproducibility Checklist

- Record exact model tags (for example, `qwen3.5:35b`, `glm-4.7-flash:q8_0`)
- Record `OLLAMA_HOST`
- Record prompt profile (`detector_prompt_v2_risk_first`)
- Keep per-run results in separate folders to avoid overwrite
- Recompute merged metrics after any targeted rerun

## Notes

- Keep only reusable code + compact results in Git.
- Large/generated artifacts (`datasets/raw`, `datasets/derived`, `work`, intermediate run trees) are normally excluded.

