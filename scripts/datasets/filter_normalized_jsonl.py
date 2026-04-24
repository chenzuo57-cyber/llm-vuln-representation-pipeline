from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import read_jsonl, write_jsonl  # noqa: E402


def _load_cwe_ids_from_json_config(path: Path) -> list[str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    ids = obj.get("cwe_ids")
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        raise ValueError(f"Config missing cwe_ids: [string, ...] in {path}")
    return ids


def _cap_per_cwe_label(
    rows: list[dict], *, max_per_cwe_label: Optional[int]
) -> list[dict]:
    if max_per_cwe_label is None:
        return rows

    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        cwe = r.get("cwe_id")
        if not isinstance(cwe, str) or not cwe:
            continue
        lab = int(r.get("label", 0))
        groups[(cwe, lab)].append(r)

    out: list[dict] = []
    for key, grp in sorted(groups.items(), key=lambda kv: kv[0]):
        grp_sorted = sorted(grp, key=lambda r: str(r.get("sample_id", "")))
        out.extend(grp_sorted[:max_per_cwe_label])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input normalized JSONL")
    ap.add_argument("--output", required=True, help="Output filtered JSONL")
    ap.add_argument(
        "--cwe-config",
        default="",
        help="JSON config containing { cwe_ids: [\"CWE-..\", ...] }",
    )
    ap.add_argument(
        "--cwe",
        action="append",
        default=[],
        help="Repeatable CWE filter, e.g. --cwe CWE-121 (overrides config if both provided)",
    )
    ap.add_argument(
        "--max-per-cwe-label",
        type=int,
        default=0,
        help="If >0, cap samples per (cwe_id, label) deterministically by sample_id sorting.",
    )
    args = ap.parse_args()

    in_p = Path(args.input)
    out_p = Path(args.output)

    cwe_ids: list[str] = []
    if args.cwe:
        cwe_ids = list(args.cwe)
    elif args.cwe_config:
        cwe_ids = _load_cwe_ids_from_json_config(Path(args.cwe_config))
    else:
        raise SystemExit("Provide --cwe (repeatable) or --cwe-config")

    allow = set(cwe_ids)

    kept: list[dict] = []
    for r in read_jsonl(in_p):
        cwe = r.get("cwe_id")
        if isinstance(cwe, str) and cwe in allow:
            kept.append(r)

    max_per = args.max_per_cwe_label if args.max_per_cwe_label > 0 else None
    kept2 = _cap_per_cwe_label(kept, max_per_cwe_label=max_per)

    write_jsonl(out_p, kept2)
    print(f"Wrote {len(kept2)} / {len(kept)} (pre-cap {len(kept)}) records to: {out_p}")


if __name__ == "__main__":
    main()
