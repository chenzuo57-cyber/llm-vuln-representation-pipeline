from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _method_suffix(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[:16]


def _safe_c_identifier(s: str) -> str:
    # Prefix ensures we don't clash with single '_' rules in some compilers.
    return f"joern_{s}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Export JSONL rows to a directory of single-function C files for joern-parse."
    )
    ap.add_argument("--input", required=True, help="Normalized JSONL with `sample_id` + `code`")
    ap.add_argument("--out-dir", required=True, help="Output directory (will contain src/ + manifest.json)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    in_p = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, str] = {}
    n = 0
    with in_p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if args.limit and n >= args.limit:
                break
            row = json.loads(line)
            sid = str(row.get("sample_id", ""))
            code = row.get("code", "")
            if not isinstance(code, str):
                code = str(code)

            suffix = _method_suffix(sid)
            fn = _safe_c_identifier(suffix)
            # One translation unit per file; wrap bare statements if needed.
            body = code.rstrip() + "\n"
            wrapped = (
                f'#line 1 "joern_snippet_{fn}.c"\n'
                f"static void {fn}(void) {{\n"
                f"{body}\n"
                f"}}\n"
            )
            c_path = out_dir / f"{fn}.c"
            c_path.write_text(wrapped, encoding="utf-8")
            manifest[fn] = sid
            n += 1

    meta = {
        "source": "prepare_joern_snippet_dir.py",
        "input": str(in_p),
        "n_files": n,
        "functions": manifest,
    }
    (out_dir / "manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {n} C files under {out_dir} and manifest {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
