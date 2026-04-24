from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


_CWE_TOKEN_RE = re.compile(r"(?i)CWE(?:-?\d+)(?:_[A-Za-z0-9_]+)?")
_CWE_TEXT_RE = re.compile(r"(?i)CWE\s*[:#-]?\s*\d+")


def _redact_cwe_tokens(text: str) -> str:
    text = _CWE_TOKEN_RE.sub("CWE_REDACTED", text)
    text = _CWE_TEXT_RE.sub("CWE_REDACTED", text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Extract only sample_id + code from normalized JSONL for LLM summarization. "
            "Preserves row order and mapping; no labels, CWE, or meta in output."
        )
    )
    ap.add_argument("--input", required=True, help="Source JSONL (must have sample_id, code)")
    ap.add_argument("--output", required=True, help="Output JSONL with {sample_id, code} only")
    ap.add_argument(
        "--numeric-id",
        action="store_true",
        help="Use simple 1-based integer id in the code file ({id, code}).",
    )
    ap.add_argument(
        "--write-id-map",
        action="store_true",
        help=(
            "With --numeric-id, also write id→sample_id JSONL (default: <output_stem>_id_map.jsonl). "
            "Otherwise recover sample_id when merging via the same subset JSONL (see merge_llm_summary_id_map.py --subset)."
        ),
    )
    ap.add_argument(
        "--map-output",
        default="",
        help="Path for id map when --write-id-map (default: <output_stem>_id_map.jsonl)",
    )
    ap.add_argument(
        "--keep-cwe",
        action="store_true",
        help="Keep CWE tokens in output code (default redacts CWE leakage markers).",
    )
    ap.add_argument("--limit", type=int, default=0, help="Optional max rows (0 = all)")
    args = ap.parse_args()
    if args.write_id_map and not args.numeric_id:
        raise SystemExit("--write-id-map requires --numeric-id")

    in_p = Path(args.input)
    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    map_p: Path | None = None
    if args.numeric_id and args.write_id_map:
        map_p = Path(args.map_output) if args.map_output else out_p.with_name(f"{out_p.stem}_id_map.jsonl")
        map_p.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with in_p.open("r", encoding="utf-8") as fin, out_p.open("w", encoding="utf-8") as fout:
        fmap = map_p.open("w", encoding="utf-8") if map_p else None
        try:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                if args.limit and n >= args.limit:
                    break
                row = json.loads(line)
                sid = str(row.get("sample_id", "")).strip()
                code = row.get("code", "")
                if not isinstance(code, str):
                    code = str(code)
                if not args.keep_cwe:
                    code = _redact_cwe_tokens(code)
                if args.numeric_id:
                    rec_id = n + 1
                    out = {"id": rec_id, "code": code}
                    if fmap is not None:
                        fmap.write(json.dumps({"id": rec_id, "sample_id": sid}, ensure_ascii=False) + "\n")
                else:
                    out = {"sample_id": sid, "code": code}
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                n += 1
        finally:
            if fmap is not None:
                fmap.close()

    print(f"Wrote {n} rows to {out_p}")
    if map_p is not None:
        print(f"Wrote id map to {map_p}")


if __name__ == "__main__":
    main()
