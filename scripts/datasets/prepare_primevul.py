from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import DATASETS_DIR, write_jsonl  # noqa: E402


_CWE_RE = re.compile(r"(CWE-\d+)")


def _iter_primevul_rows(path: Path) -> Iterator[dict]:
    """
    PrimeVul JSONL includes very large integer fields like func_hash.
    orjson may coerce these to floats and lose precision, so we parse with stdlib json.
    """
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _intish_to_str(v: Any) -> Optional[str]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # Should be rare after switching to stdlib json, but keep a safe fallback.
        if v.is_integer():
            return str(int(v))
        return None
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _pick_first(d: dict, keys: list[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _normalize_cwe(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list):
        for item in v:
            c = _normalize_cwe(item)
            if c:
                return c
        return None
    if isinstance(v, (int, float)) and int(v) == v:
        return f"CWE-{int(v)}"
    s = str(v).strip()
    m = _CWE_RE.search(s)
    return m.group(1) if m else None


def _normalize_label(v: Any) -> int:
    # PrimeVul typically uses 1 for vulnerable, 0 for benign.
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return 1 if int(v) == 1 else 0
    s = str(v).strip().lower()
    if s in {"1", "true", "vul", "vulnerable", "bad"}:
        return 1
    if s in {"0", "false", "benign", "good", "clean"}:
        return 0
    raise ValueError(f"Unrecognized label: {v!r}")


def normalize_primevul_split(path: Path, split: str) -> list[dict]:
    out: list[dict] = []
    for row in _iter_primevul_rows(path):
        fh = row.get("func_hash")
        sample_id_s = _intish_to_str(fh)
        if sample_id_s is None:
            sample_id = _pick_first(row, ["sample_id", "id", "idx"])
        else:
            sample_id = sample_id_s
        if sample_id is None:
            # Fall back to stable-ish hash of code if present.
            code_for_hash = _pick_first(row, ["func", "code", "function", "src"])
            sample_id = f"primevul:{split}:{hash(str(code_for_hash))}"
        sample_id = str(sample_id)

        code = _pick_first(row, ["func", "code", "function", "src"])
        if code is None:
            # PrimeVul-v0.1 may store only pointers into file_contents/; keep record but mark missing.
            code = ""

        label_raw = _pick_first(row, ["target", "label", "vul", "is_vul"])
        if label_raw is None:
            raise RuntimeError(f"Missing label fields in row with sample_id={sample_id}")
        label = _normalize_label(label_raw)

        cwe = _normalize_cwe(_pick_first(row, ["cwe", "cwe_id", "cweid", "cwe_id_list", "cwe_list", "cwe_number"]))

        language = _pick_first(row, ["language", "lang"])
        if language is not None:
            language = str(language).strip().lower()
            if language in {"c", "c++", "cpp"}:
                language = "cpp" if language in {"c++", "cpp"} else "c"
            else:
                language = None

        out.append(
            {
                "dataset": "primevul",
                "split": split,
                "sample_id": sample_id,
                "label": label,
                "cwe_id": cwe,
                "language": language,
                "code": str(code),
                "meta": row,
            }
        )
    return out


def main() -> None:
    raw_dir = DATASETS_DIR / "primevul" / "raw"
    train_p = raw_dir / "primevul_train.jsonl"
    valid_p = raw_dir / "primevul_valid.jsonl"
    test_p = raw_dir / "primevul_test.jsonl"
    for p in [train_p, valid_p, test_p]:
        if not p.exists():
            raise SystemExit(f"Missing {p}. Run: python3 scripts/datasets/download_primevul.py")

    prepared_dir = DATASETS_DIR / "primevul" / "prepared"
    out_train = prepared_dir / "primevul_train_normalized.jsonl"
    out_valid = prepared_dir / "primevul_valid_normalized.jsonl"
    out_test = prepared_dir / "primevul_test_normalized.jsonl"

    train_rows = normalize_primevul_split(train_p, "train")
    write_jsonl(out_train, train_rows)
    print(f"Wrote {len(train_rows)} records to: {out_train}")

    valid_rows = normalize_primevul_split(valid_p, "valid")
    write_jsonl(out_valid, valid_rows)
    print(f"Wrote {len(valid_rows)} records to: {out_valid}")

    test_rows = normalize_primevul_split(test_p, "test")
    write_jsonl(out_test, test_rows)
    print(f"Wrote {len(test_rows)} records to: {out_test}")


if __name__ == "__main__":
    main()

