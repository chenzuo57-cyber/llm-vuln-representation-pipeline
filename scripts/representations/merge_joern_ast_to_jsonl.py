from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Merge Joern per-method .ast.txt files back into JSONL using manifest.json."
    )
    ap.add_argument("--input", required=True, help="Original normalized JSONL")
    ap.add_argument("--manifest", required=True, help="manifest.json from prepare_joern_snippet_dir.py")
    ap.add_argument("--ast-dir", required=True, help="Directory with joern_<hex>.ast.txt from joern_dump_ast.sc")
    ap.add_argument("--output", required=True, help="Output JSONL with ast_joern_text")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    fn_to_sid: dict[str, str] = manifest["functions"]
    sid_to_fn = {v: k for k, v in fn_to_sid.items()}
    ast_dir = Path(args.ast_dir)

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    missing = 0
    with Path(args.input).open("r", encoding="utf-8") as fin, out_p.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            sid = str(row.get("sample_id", ""))
            fn = sid_to_fn.get(sid)
            ast_text = ""
            err = ""
            if fn is None:
                err = "sample_id_not_in_manifest"
                missing += 1
            else:
                p = ast_dir / f"{fn}.ast.txt"
                if p.exists():
                    ast_text = p.read_text(encoding="utf-8", errors="replace")
                else:
                    err = "ast_file_missing"
                    missing += 1

            out = dict(row)
            out["representation"] = "ast_joern"
            out["ast_joern_text"] = ast_text
            out["ast_joern_error"] = err
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} rows to {out_p} (ast missing/issues: {missing})")


if __name__ == "__main__":
    main()
