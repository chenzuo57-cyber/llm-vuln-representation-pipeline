# Phd-A2: Reproducible Vulnerability Representation Pipeline

This repository provides an end-to-end pipeline to reproduce vulnerability-detection experiments across multiple code representations and LLM backends.

**Article 2 evaluation** uses **five** test corpora (Juliet, PrimeVul, MegaVul, RDiverseVul, ReposVul competition test). This git repo ships scripts for **Juliet + PrimeVul**; extension benchmarks are downloaded locally and built into frozen splits (checksums and links in [Article 2 — five test datasets](#article-2--five-test-datasets-acquisition-and-filtering)).

## Scope

- Datasets (Article 2 test splits — **79,059** rows total across five JSONL; not bundled in git):
  - **PrimeVul** — primary; official **test** CWE subset (**15,668** rows)
  - **Juliet** v1.3 C/C++ — secondary Article 2 subset (**8,410** rows)
  - **MegaVul** — extension; stratified **20,000**-row frozen split (seed `20261012`)
  - **RDiverseVul** — extension; stratified **20,000**-row frozen split (same seed)
  - **ReposVul** — competition C/C++ **test**; **15,981** rows after cross-benchmark filters
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
  - `juliet/`, `primevul/` — built via tracked download/prepare scripts
  - `benchmarks/` — MegaVul, RDiverseVul, ReposVul upstream + `prepared/frozen_v1/` Article 2 splits (local only)
- `work/`, `workspace/`: transient Joern/runtime artifacts

## Folder and File Structure Guide

This section shows the **minimal git surface** for Juliet + PrimeVul reproduction. Article 2 adds three more benchmarks (download + frozen JSONL); see [five test datasets](#article-2--five-test-datasets-acquisition-and-filtering).

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
└── datasets/   (juliet, primevul, benchmarks/ — local; see Scope)
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
- Remote example: `http://<ollama-host>:11434`

Quick connectivity check:

```bash
curl -s http://127.0.0.1:11434/api/tags
```

Or remote:

```bash
curl -s "http://<ollama-host>:11434/api/tags"
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

## Article 2 — five test datasets (acquisition and filtering)

Large corpora and frozen evaluation JSONL are **not** stored in this repository (size and third-party licenses). Use the steps below to download upstream data, understand our filters, and verify the **test splits** we use in Article 2.

### Summary (evaluation test splits)

| Dataset | Split file (local path after build) | Rows | SHA-256 |
|---------|-----------------------------------|-----:|---------|
| Juliet | `datasets/juliet/prepared/juliet_article2_subset.jsonl` | 8,410 | `8773e985e64c773d619b75bd1f09ed1361e4dea357424321f73cfce0e9d0a198` |
| PrimeVul (official **test** only) | `datasets/primevul/prepared/primevul_test_article2_subset.jsonl` | 15,668 | `80deb52ba5ae625d4f561f991cf10353b519c9f9743908d7bf6c1627013dda1b` |
| MegaVul | `datasets/benchmarks/prepared/frozen_v1/megavul_frozen_v1_prepared.jsonl` | 20,000 | `5f1616eb9a6a738a86952aec01b21d5d04edcd6261e5adddacbdb4af092d5169` |
| RDiverseVul | `datasets/benchmarks/prepared/frozen_v1/rdiversevul_frozen_v1_prepared.jsonl` | 20,000 | `9c8d76ccca3d3150051fc5d1139c8bea43e496b3ddaad96cc71ceadfee47c219` |
| ReposVul (competition **test**) | `datasets/benchmarks/prepared/frozen_v1/reposvul_test_frozen_v1_prepared.jsonl` | 15,981 | `d51b5e6184ec9a20e13ea48f34bad9c1df402878061545c409cc5cb4a95de94b` |

Juliet and PrimeVul splits are produced with the commands in [§1 Download and Prepare Datasets](#1-download-and-prepare-datasets) and the CWE configs under `configs/`. The three extension splits are built locally (see below); **contact the authors or use the paper supplementary archive** if you need the frozen JSONL without re-running the full pipeline.

### Download upstream sources

| Dataset | Where to download | Place on disk (default paths used by our tooling) |
|---------|-------------------|---------------------------------------------------|
| **PrimeVul** | `python3 scripts/datasets/download_primevul.py` | `datasets/primevul/` (then `prepare_primevul.py`) |
| **Juliet** | `python3 scripts/datasets/download_juliet.py` | `datasets/juliet/` (then `prepare_juliet.py`) |
| **MegaVul** | [Icyrockton/MegaVul](https://github.com/Icyrockton/MegaVul) — obtain `megavul_simple.json` from the project’s linked release / cloud drive (see their `SPECIFICATION.md`) | Any path; our profiling defaults to `~/Downloads/megavul_simple.json` or pass `--megavul` |
| **RDiverseVul** | Zenodo [10.5281/zenodo.15051277](https://doi.org/10.5281/zenodo.15051277) — file `RDiverseVul.json` (~493 MB; MD5 `48965ed417cf1ec9389e010a91412f7f`) | `datasets/benchmarks/rdiversevul/RDiverseVul.json` |
| **ReposVul** | [Eshe0922/ReposVul](https://github.com/Eshe0922/ReposVul) — competition C/C++ archive (Google Drive link in that README) | Extract so the official test JSONL is at `datasets/benchmarks/reposvul/competition/random/test_c_cpp_repository2.jsonl` |

Check each dataset’s license before redistributing code snippets or derived manifests.

### Screening and test-set construction (Article 2)

Processing order (implementation lives under `scripts/datasets/` in the maintainer tree; outputs are local):

1. **Normalize code** — whitespace-normalized `norm_hash` per function/snippet (same idea as Juliet/PrimeVul dedup).
2. **Cross-benchmark dedup** — build candidate pools for MegaVul, RDiverseVul, and ReposVul test; assign duplicate hashes to a single **owner** with priority **ReposVul test → RDiverseVul → MegaVul** (`cross_benchmark_dedup.py` → `results/benchmark_profile/cross_dedup/`).
3. **Cross-dataset label conflicts (V6)** — globally drop **896** hashes that appear with disagreeing labels across datasets before evaluation sampling.
4. **CWE shortlist (strategy B)** — keep CWEs with at least **100 vulnerable** training/evaluation-eligible rows in that dataset; for RDiverseVul also **drop rows whose primary CWE is unknown/missing** (strategy B, not B+).
5. **ReposVul** — use the full eligible official **test** split after steps 2–3 (**15,981** rows).
6. **MegaVul & RDiverseVul** — stratified sample **20,000** rows each with seed **`20261012`**, strata `(label, primary_cwe)`, proportional allocation (`build_proposed_evaluation_manifests.py` policy `researcher_approved_2026-10-12`).

MegaVul code field: `func_before` when `is_vul` else `func`; label = `is_vul` ([MegaVul spec](https://github.com/Icyrockton/MegaVul/blob/main/SPECIFICATION.md)).

### Obtain our frozen test JSONL

- **Reproduce:** run the pipeline above on your downloaded upstream files; materialize prepared splits under `datasets/benchmarks/prepared/frozen_v1/` and compare SHA-256 to the table.
- **Without rebuilding:** use the checksums in the table to verify copies from the **paper supplementary package** or a data release published with the Article 2 preprint (not committed here).
- **Status:** Juliet/PrimeVul Article 2 subsets and published 7×2 pilot results are **frozen**; extension benchmarks are **defined and checksum’d** as above — full 7×2 on MegaVul/RDiverseVul/ReposVul may still be in progress.

## Notes

- Keep only reusable code + compact results in Git.
- Large/generated artifacts (`datasets/raw`, `datasets/derived`, `work`, intermediate run trees) are normally excluded.

