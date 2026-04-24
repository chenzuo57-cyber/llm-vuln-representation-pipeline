from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import DATASETS_DIR, DownloadSpec, download_file, ensure_dir  # noqa: E402


def main() -> None:
    out_dir = DATASETS_DIR / "primevul" / "raw"
    ensure_dir(out_dir)

    # Hugging Face mirror (direct file resolves; no auth; easiest to script).
    # Source: https://huggingface.co/datasets/colin/PrimeVul/tree/main
    base = "https://huggingface.co/datasets/colin/PrimeVul/resolve/main"
    files = [
        "primevul_train.jsonl",
        "primevul_valid.jsonl",
        "primevul_test.jsonl",
        "file_info.json",
    ]

    for name in files:
        url = f"{base}/{name}"
        dest = out_dir / name
        download_file(DownloadSpec(url=url, dest=dest, min_bytes=1024))

    print(f"PrimeVul downloaded to: {out_dir}")


if __name__ == "__main__":
    main()

