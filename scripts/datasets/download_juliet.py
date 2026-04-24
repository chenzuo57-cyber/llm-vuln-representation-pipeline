from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datasets._common import DATASETS_DIR, DownloadSpec, download_file, ensure_dir  # noqa: E402


def main() -> None:
    out_dir = DATASETS_DIR / "juliet" / "raw"
    ensure_dir(out_dir)

    # Zenodo mirror of the official NIST SARD Juliet v1.3 zip.
    # Record: https://zenodo.org/records/4701387
    # SHA256 from NIST SARD listing.
    url = "https://zenodo.org/records/4701387/files/Juliet_Test_Suite_v1.3_for_C_Cpp.zip?download=1"
    dest = out_dir / "Juliet_Test_Suite_v1.3_for_C_Cpp.zip"
    sha256 = "ada9d7e1c323d283446df3f55bdee0d00bda1fed786785fe98764d58688f38eb"

    download_file(
        DownloadSpec(
            url=url,
            dest=dest,
            sha256=sha256,
            min_bytes=10 * 1024 * 1024,  # sanity check: should be ~150MB
        )
    )

    print(f"Juliet zip downloaded to: {dest}")
    print("Next: unzip it into datasets/juliet/raw/extracted/ (prepare_juliet.py can do this).")


if __name__ == "__main__":
    main()

