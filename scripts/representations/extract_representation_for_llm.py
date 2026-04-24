from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REP_FIELD = {
    "ast": "ast_joern_text",
    "cfg": "cfg_joern_text",
    "dfg": "dfg_joern_text",
    "cpg": "cpg_joern_text",
    "slice": "slice_joern_text",
}


_CWE_TOKEN_RE = re.compile(r"(?i)CWE(?:-?\d+)(?:_[A-Za-z0-9_]+)?")
_CWE_TEXT_RE = re.compile(r"(?i)CWE\s*[:#-]?\s*\d+")


def _redact_cwe_tokens(text: str) -> str:
    text = _CWE_TOKEN_RE.sub("CWE_REDACTED", text)
    text = _CWE_TEXT_RE.sub("CWE_REDACTED", text)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract {id,text} from representation JSONL for LLM prompting."
    )
    ap.add_argument("--input", required=True, help="Source representation JSONL")
    ap.add_argument("--output", required=True, help="Output JSONL with only id,text")
    ap.add_argument(
        "--representation",
        required=True,
        choices=sorted(REP_FIELD.keys()),
        help="Representation kind: ast/cfg/dfg/cpg/slice",
    )
    ap.add_argument(
        "--keep-cwe",
        action="store_true",
        help="Keep CWE tokens in output text (default redacts CWE leakage markers).",
    )
    ap.add_argument("--limit", type=int, default=0, help="Optional max rows (0 = all)")
    args = ap.parse_args()

    in_p = Path(args.input)
    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    text_key = REP_FIELD[args.representation]
    n = 0
    with in_p.open("r", encoding="utf-8") as fin, out_p.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            if args.limit and n >= args.limit:
                break
            row = json.loads(line)
            rid = row.get("id")
            if rid is None:
                raise SystemExit(f"Missing id at row {n + 1} in {in_p}")
            text = row.get(text_key, "")
            if not isinstance(text, str):
                text = str(text)
            if not args.keep_cwe:
                text = _redact_cwe_tokens(text)
            fout.write(json.dumps({"id": int(rid), "text": text}, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} rows to {out_p}")


if __name__ == "__main__":
    main()
