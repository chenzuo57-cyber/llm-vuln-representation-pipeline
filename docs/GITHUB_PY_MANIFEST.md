# Python files — GitHub publication surface

**Date:** 2026-11-24  
**Policy:** Match `README.md` reproduction scope. Everything else stays local (`.gitignore`).

## Approved `.py` files (22)

| Area | Files |
|------|--------|
| Package stubs | `scripts/__init__.py`, `scripts/datasets/__init__.py`, `scripts/representations/__init__.py` |
| Datasets | `_common.py`, `dataset_stats.py`, `download_juliet.py`, `download_primevul.py`, `filter_normalized_jsonl.py`, `prepare_juliet.py`, `prepare_primevul.py` |
| Representations | `extract_code_for_llm.py`, `extract_representation_for_llm.py`, `generate_llm_summary_ollama.py`, `merge_joern_*_to_jsonl.py` (5), `merge_llm_summary_id_map.py`, `normalize_code_for_llm_jsonl.py`, `prepare_joern_snippet_dir.py` |
| Evaluation | `run_inference_all.py` |

Paths are under `scripts/datasets/`, `scripts/representations/`, `scripts/evaluation/` as listed in the repository README.

## Not on GitHub

- Any path matching `*qwen*` / `*Qwen*` (configs, results, scripts).
- `scripts/article2/`, `scripts/validation/`, `scripts/inference/` (including `test_*.py`).
- Other `scripts/datasets/*.py` (pilots, launches, audits — 200+ local one-offs).
- `scripts/evaluation/export_matrix_individual.py`, Joern v2 micropilot helpers.

## Remove from remote (already tracked)

Run before the next publication commit (working tree unchanged):

```bash
git rm -r --cached results/
```

Legacy pilot `*_predictions.jsonl` under `results/juliet/` and `results/primevul/` (GLM + Qwen) should not remain on `origin/main`.

## Verify

```bash
git ls-files '*.py' | wc -l   # expect 22
git add -n . | rg '^add ' | rg '\.py$'
```

Only paths in **Approved** should appear.
