from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Join LLM summary JSONL (rows with numeric id) to add sample_id for merging into full dataset rows. "
            "Provide either --subset (same JSONL order as code_for_llm, id =1-based line index) or --id-map."
        )
    )
    ap.add_argument("--summary", required=True, help="Output from generate_llm_summary_ollama.py (has id)")
    ap.add_argument("--id-map", default="", help="Optional id→sample_id JSONL from extract_code_for_llm --write-id-map")
    ap.add_argument(
        "--subset",
        default="",
        help="Optional full subset JSONL (e.g. juliet_article2_subset.jsonl); builds id→sample_id from row order",
    )
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    if bool(args.id_map) == bool(args.subset):
        raise SystemExit("Provide exactly one of --id-map or --subset")

    id_to_sid: dict[int, str] = {}
    if args.id_map:
        with Path(args.id_map).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                id_to_sid[int(o["id"])] = str(o["sample_id"])
    else:
        idx = 0
        with Path(args.subset).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                idx += 1
                o = json.loads(line)
                id_to_sid[idx] = str(o.get("sample_id", ""))

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    miss = 0
    with Path(args.summary).open("r", encoding="utf-8") as fin, out_p.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rid = row.get("id")
            if rid is None:
                miss += 1
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
                continue
            sid = id_to_sid.get(int(rid))
            if sid is None:
                miss += 1
            else:
                row["sample_id"] = sid
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} rows to {out_p} (missing id map: {miss})")


if __name__ == "__main__":
    main()
