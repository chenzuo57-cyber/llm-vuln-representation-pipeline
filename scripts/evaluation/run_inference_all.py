#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

REPRESENTATIONS = ["rawcode", "ast", "cfg", "dfg", "cpg", "slice", "llm_summary"]
DATASETS = ["primevul", "juliet"]

PROMPT_TEMPLATE_V2 = """You are a vulnerability detection assistant.
Given one code representation snippet, decide whether vulnerable-like behavior is present.

Decision policy:
- Predict 1 when there is direct evidence of unsafe behavior OR missing validation on a risky path.
- Predict 1 for patterns such as unchecked pointer dereference, unbounded copy/write, out-of-bounds index risk, size/length mismatch, integer overflow/underflow risk, use-after-free/double-free risk, null-deref risk, tainted input reaching dangerous sink/API, or allocation/use with weak bounds checks.
- Predict 0 only when the snippet has clear safeguards that specifically block the risky path.
- If evidence is partial/ambiguous but still plausibly unsafe, prefer 1.
- Base the decision only on visible snippet evidence.

Output format (exactly two lines, no extras):
Prediction: <0 or 1>
Reason: <one short sentence citing concrete snippet evidence>

Do not mention CWE IDs, datasets, confidence scores, or any additional text.

Representation: {representation}
Snippet:
{text}
"""

PROMPT_TEMPLATE_V1 = """You are a vulnerability detection assistant.
Given one code representation snippet, predict whether it indicates an exploitable vulnerability.
Return exactly two lines in this exact format:
Prediction: <0 or 1>
Reason: <one concise sentence based only on the provided snippet>
Where 1 means vulnerable and 0 means not vulnerable.
Do not mention CWE IDs or dataset labels.
Do not output anything else.

Representation: {representation}
Snippet:
{text}
"""


def _resolve_prompt(prompt_profile: str) -> tuple[str, str, str]:
    profile = (prompt_profile or "").strip().lower()
    if profile == "detector_prompt_v1_exploitability":
        template = PROMPT_TEMPLATE_V1
        version = "detector_prompt_v1_exploitability"
    elif profile == "detector_prompt_v2_risk_first":
        template = PROMPT_TEMPLATE_V2
        version = "detector_prompt_v2_risk_first"
    else:
        raise SystemExit(
            "Unknown --prompt-profile. Use detector_prompt_v2_risk_first (default). "
            "Legacy v1 is disabled unless ALLOW_DEPRECATED_V1_PROMPT=1."
        )
    return template, version, hashlib.sha256(template.encode("utf-8")).hexdigest()


def _post_ollama(host: str, model: str, prompt: str, timeout_s: int, num_predict: int, temperature: float) -> dict[str, Any]:
    url = host.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _parse_prediction(text: str) -> tuple[int | None, str, str]:
    out = (text or "").strip()
    if not out:
        return None, "parse_error", "empty_output"
    m = re.search(r"Prediction\s*:\s*([01])", out, flags=re.IGNORECASE)
    if m:
        return int(m.group(1)), "ok", ""
    low = out.lower()
    if "not vulnerable" in low or "safe" in low:
        return 0, "heuristic_ok", ""
    if "vulnerable" in low:
        return 1, "heuristic_ok", ""
    m2 = re.search(r"\b([01])\b", out)
    if m2:
        return int(m2.group(1)), "heuristic_ok", ""
    return None, "parse_error", "unable_to_parse_prediction"


def _extract_reason(text: str) -> str:
    out = (text or "").strip()
    if not out:
        return ""
    m = re.search(r"Reason\s*:\s*(.+)", out, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[1] if len(lines) >= 2 else ""


def _resolve_rep_path(eval_dir: Path, dataset: str, rep: str, smoke_test: bool, input_suffix: str) -> Path:
    suffix = "_test20" if smoke_test else input_suffix
    stem = f"{rep}_for_llm_{dataset}{suffix}.jsonl"
    candidates = [
        eval_dir / stem,
        eval_dir / "datasets" / "derived" / f"{dataset}_article2" / stem,
        eval_dir / "datasets" / stem,
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Inference-only vulnerability predictions across representations.")
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-predict", type=int, default=64)
    ap.add_argument("--timeout-s", type=int, default=300)
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument("--eval-dir", default=".")
    ap.add_argument("--results-dir", default="results_inference")
    ap.add_argument("--representations", default=",".join(REPRESENTATIONS))
    ap.add_argument("--datasets", default=",".join(DATASETS))
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument(
        "--prompt-profile",
        default="detector_prompt_v2_risk_first",
        help="Use detector_prompt_v2_risk_first. Legacy v1 requires ALLOW_DEPRECATED_V1_PROMPT=1.",
    )
    ap.add_argument("--input-suffix", default="", help="Optional suffix for non-smoke input files, e.g. _test500")
    args = ap.parse_args()

    prof = (args.prompt_profile or "").strip().lower()
    if prof == "detector_prompt_v1_exploitability" and os.environ.get("ALLOW_DEPRECATED_V1_PROMPT") != "1":
        raise SystemExit(
            "Prompt v1 is disabled. Use --prompt-profile detector_prompt_v2_risk_first, "
            "or set ALLOW_DEPRECATED_V1_PROMPT=1 to run legacy v1."
        )

    eval_dir = Path(args.eval_dir).resolve()
    results_root = Path(args.results_dir).resolve()
    prompt_template, prompt_version, prompt_sha256 = _resolve_prompt(args.prompt_profile)
    reps = [r.strip() for r in args.representations.split(",") if r.strip()]
    dsets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    results_root.mkdir(parents=True, exist_ok=True)

    for dataset in dsets:
        ds_out = results_root / dataset
        ds_out.mkdir(parents=True, exist_ok=True)
        for rep in reps:
            in_path = _resolve_rep_path(eval_dir, dataset, rep, args.smoke_test, args.input_suffix)
            if not in_path.exists():
                print(f"[skip] missing input: {in_path}")
                continue
            rows = _load_jsonl(in_path)
            if args.max_rows > 0:
                rows = rows[: args.max_rows]
            pred_path = ds_out / f"{rep}_predictions.jsonl"
            err_path = results_root / f"error_cases_{dataset}_{rep}.jsonl"
            parse_fail = 0
            with pred_path.open("w", encoding="utf-8") as f_pred, err_path.open("w", encoding="utf-8") as f_err:
                for row in rows:
                    rid = str(row.get("id", "")).strip()
                    text = str(row.get("text", row.get("code", "")) or "")
                    prompt = prompt_template.format(representation=rep, text=text)
                    raw_output = ""
                    parse_status = "ok"
                    parse_error = ""
                    pred = None
                    reason = ""
                    try:
                        obj = _post_ollama(args.host, args.model, prompt, args.timeout_s, args.num_predict, args.temperature)
                        raw_output = str(obj.get("response", "")).strip()
                        pred, parse_status, parse_error = _parse_prediction(raw_output)
                        reason = _extract_reason(raw_output)
                    except Exception as e:  # noqa: BLE001
                        parse_status = "request_error"
                        parse_error = str(e)
                    if pred is None:
                        parse_fail += 1
                    out = {
                        "id": rid,
                        "predicted_label": pred,
                        "reason": reason,
                        "raw_model_output": raw_output,
                        "parse_status": parse_status,
                        "parse_error": parse_error,
                        "prompt_version": prompt_version,
                        "prompt_sha256": prompt_sha256,
                    }
                    f_pred.write(json.dumps(out, ensure_ascii=False) + "\n")
                    if parse_status != "ok":
                        f_err.write(json.dumps({"dataset": dataset, "representation": rep, **out}, ensure_ascii=False) + "\n")
            print(f"done dataset={dataset} rep={rep} rows={len(rows)} parse_fail={parse_fail}")


if __name__ == "__main__":
    main()

