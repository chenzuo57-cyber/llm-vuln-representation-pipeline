from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Rewrite code-for-LLM JSONL to exactly {id, code} per line (drops sample_id and other keys)."
    )
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    in_p, out_p = Path(args.input), Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with in_p.open("r", encoding="utf-8") as fin, out_p.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "id" not in row:
                raise SystemExit("row missing id")
            code = row.get("code", "")
            if not isinstance(code, str):
                code = str(code)
            if not code.strip():
                raise SystemExit(f"row id={row.get('id')} missing code")
            fout.write(json.dumps({"id": row["id"], "code": code}, ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} rows to {out_p}")


if __name__ == "__main__":
    main()
