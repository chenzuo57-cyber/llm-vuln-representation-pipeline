from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import read_jsonl  # noqa: E402


def iter_paths(p: Path) -> Iterable[Path]:
    if p.is_file():
        yield p
        return
    for child in sorted(p.rglob("*.jsonl")):
        yield child


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=str, help="JSONL file or directory containing JSONL files")
    ap.add_argument("--topk", type=int, default=15)
    args = ap.parse_args()

    paths = list(iter_paths(Path(args.path)))
    if not paths:
        raise SystemExit(f"No .jsonl files found under: {args.path}")

    total = 0
    vuln = 0
    benign = 0
    missing_code = 0
    cwe_counter: Counter[str] = Counter()
    by_dataset: Counter[str] = Counter()

    for p in paths:
        for r in read_jsonl(p):
            total += 1
            by_dataset[str(r.get("dataset", "unknown"))] += 1
            label = int(r.get("label", 0))
            if label == 1:
                vuln += 1
            else:
                benign += 1
            code = r.get("code", "")
            if not isinstance(code, str) or len(code.strip()) == 0:
                missing_code += 1
            cwe = r.get("cwe_id")
            if isinstance(cwe, str) and cwe:
                cwe_counter[cwe] += 1

    print(f"files: {len(paths)}")
    print(f"records: {total}")
    print(f"label: vuln={vuln} benign={benign} vuln_rate={(vuln/total if total else 0):.4f}")
    print(f"missing_code: {missing_code} ({(missing_code/total if total else 0):.4f})")
    print("by_dataset:")
    for k, v in by_dataset.most_common():
        print(f"  {k}: {v}")
    print(f"top_cwe (top {args.topk}):")
    for cwe, n in cwe_counter.most_common(args.topk):
        print(f"  {cwe}: {n}")


if __name__ == "__main__":
    main()

