from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import DATASETS_DIR, ensure_dir, sha256_file, write_jsonl  # noqa: E402


_CWE_DIR_RE = re.compile(r"(CWE\d+)")
_CWE_NUM_RE = re.compile(r"CWE(\d+)")
_JULIET_V13_SHA256 = "ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb"


def _find_juliet_zip(raw_dir: Path) -> Path:
    preferred = [
        raw_dir / "Juliet_Test_Suite_v1.3_for_C_Cpp.zip",
        raw_dir / "2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip",
    ]
    for p in preferred:
        if p.exists():
            return p

    matches = sorted(raw_dir.glob("*.zip"))
    for p in matches:
        low = p.name.lower()
        if "juliet" in low and ("c" in low or "cpp" in low or "cplusplus" in low):
            return p

    raise FileNotFoundError(
        "Could not find a Juliet v1.3 zip in "
        f"{raw_dir}. Expected one of:\n"
        f"- {preferred[0].name}\n"
        f"- {preferred[1].name}\n"
        "Or place any matching `*juliet*...*.zip` in that folder."
    )


def _cwe_from_path(p: Path) -> Optional[str]:
    # Juliet directory names usually contain CWE###, e.g. CWE121_Stack_Based_Buffer_Overflow
    m = _CWE_DIR_RE.search(str(p).replace("\\", "/"))
    if not m:
        return None
    m2 = _CWE_NUM_RE.search(m.group(1))
    if not m2:
        return None
    return f"CWE-{m2.group(1)}"


def _label_from_filename(name: str) -> Optional[int]:
    # Juliet naming convention often includes good/bad.
    low = name.lower()
    if "good" in low:
        return 0
    if "bad" in low:
        return 1
    return None


def _iter_source_files(root: Path) -> Iterable[Path]:
    for ext in (".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"):
        yield from root.rglob(f"*{ext}")


def _scan_roots_for_juliet(suite_root: Path) -> list[Path]:
    """
    Juliet ships a large amount of harness/support code. For VD benchmarks, the labeled
    good/bad variants are typically under **/testcases/**.
    """
    roots: list[Path] = []
    for candidate in (
        suite_root / "C" / "testcases",
        suite_root / "Cpp" / "testcases",
        suite_root / "C++" / "testcases",
        suite_root / "testcases",
    ):
        if candidate.exists() and candidate.is_dir():
            roots.append(candidate)

    # Fallback: some archives may unpack flat; if no testcases dirs found, scan suite_root.
    return roots if roots else [suite_root]


def unzip_if_needed(zip_path: Path, extracted_dir: Path) -> None:
    if extracted_dir.exists() and any(extracted_dir.iterdir()):
        return
    ensure_dir(extracted_dir)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extracted_dir)


def main() -> None:
    raw_dir = DATASETS_DIR / "juliet" / "raw"
    zip_path = _find_juliet_zip(raw_dir)
    got = sha256_file(zip_path)
    if got.lower() != _JULIET_V13_SHA256.lower():
        raise SystemExit(
            "Juliet zip SHA256 does not match the official Juliet C/C++ v1.3 listing.\n"
            f"- path: {zip_path}\n"
            f"- expected: {_JULIET_V13_SHA256}\n"
            f"- got: {got}"
        )

    extracted_dir = raw_dir / "extracted"
    unzip_if_needed(zip_path, extracted_dir)

    # Heuristic: find the main test suite directory within extracted.
    # Typical structure includes something like: Juliet_Test_Suite_v1.3_for_C_Cpp/
    candidates = [p for p in extracted_dir.iterdir() if p.is_dir()]
    suite_root = candidates[0] if len(candidates) == 1 else extracted_dir

    out_rows: list[dict] = []
    scan_roots = _scan_roots_for_juliet(suite_root)
    for scan_root in scan_roots:
        for src_path in _iter_source_files(scan_root):
            label = _label_from_filename(src_path.name)
            if label is None:
                continue
            cwe = _cwe_from_path(src_path)
            if cwe is None:
                continue

            try:
                code = src_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lang = "c"
            if src_path.suffix.lower() in {".cpp", ".cc", ".cxx", ".hpp"}:
                lang = "cpp"

            # This is file-level; we keep meta so later you can choose a function-level extraction policy.
            sample_id = f"juliet:{cwe}:{src_path.as_posix()}"
            out_rows.append(
                {
                    "dataset": "juliet",
                    "split": "unsplit",
                    "sample_id": sample_id,
                    "label": label,
                    "cwe_id": cwe,
                    "language": lang,
                    "code": code,
                    "meta": {
                        "path": src_path.as_posix(),
                        "filename": src_path.name,
                        "scan_root": scan_root.as_posix(),
                    },
                }
            )

    prepared_dir = DATASETS_DIR / "juliet" / "prepared"
    out_p = prepared_dir / "juliet_normalized.jsonl"
    write_jsonl(out_p, out_rows)
    print(f"Wrote {len(out_rows)} records to: {out_p}")
    print("Note: Juliet is file-level here; next step is function-level extraction (e.g., via Joern) if needed.")


if __name__ == "__main__":
    main()

