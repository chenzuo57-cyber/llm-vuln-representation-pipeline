from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None

try:
    import orjson  # type: ignore
except Exception:  # pragma: no cover
    orjson = None


ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = ROOT / "datasets"


def dumps_json(obj: object) -> bytes:
    # PrimeVul metadata can include huge integers (e.g., func_hash) that exceed
    # orjson's supported range; stdlib json can serialize Python big ints.
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@dataclass(frozen=True)
class DownloadSpec:
    url: str
    dest: Path
    sha256: Optional[str] = None
    min_bytes: Optional[int] = None


def _http_download(url: str, dest_tmp: Path) -> None:
    headers = {
        # Helps some hosts return the real file rather than a HTML page.
        "User-Agent": "phd-a2-datasets/1.0 (+dataset prep)",
        "Accept": "*/*",
    }

    # Prefer requests: better redirect handling + streaming + Content-Length checks.
    if requests is not None:
        with requests.get(url, headers=headers, stream=True, timeout=(30, 300), allow_redirects=True) as resp:
            resp.raise_for_status()
            cl = resp.headers.get("Content-Length")
            expected = int(cl) if cl and cl.isdigit() else None

            written = 0
            with dest_tmp.open("wb") as out:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    out.write(chunk)
                    written += len(chunk)

            if expected is not None and written != expected:
                raise RuntimeError(
                    f"Incomplete download (bytes written {written} != Content-Length {expected}) for URL:\n{url}"
                )
        return

    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=300) as resp, dest_tmp.open("wb") as out:
        expected = resp.headers.get("Content-Length")
        expected_n = int(expected) if expected and expected.isdigit() else None
        written = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)
        if expected_n is not None and written != expected_n:
            raise RuntimeError(
                f"Incomplete download (bytes written {written} != Content-Length {expected_n}) for URL:\n{url}"
            )


def download_file(spec: DownloadSpec, *, force: bool = False) -> Path:
    ensure_dir(spec.dest.parent)

    if spec.dest.exists() and not force:
        if spec.min_bytes is not None and spec.dest.stat().st_size < spec.min_bytes:
            raise RuntimeError(f"Existing file too small: {spec.dest}")
        if spec.sha256 is not None:
            got = sha256_file(spec.dest)
            if got.lower() != spec.sha256.lower():
                raise RuntimeError(
                    f"SHA256 mismatch for existing file:\n"
                    f"- path: {spec.dest}\n"
                    f"- expected: {spec.sha256}\n"
                    f"- got: {got}"
                )
        return spec.dest

    dest_tmp = spec.dest.with_suffix(spec.dest.suffix + ".part")
    if dest_tmp.exists():
        dest_tmp.unlink()

    t0 = time.time()
    try:
        _http_download(spec.url, dest_tmp)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Download failed: {spec.url}\n{e}") from e

    if spec.min_bytes is not None and dest_tmp.stat().st_size < spec.min_bytes:
        raise RuntimeError(f"Downloaded file too small: {dest_tmp} ({dest_tmp.stat().st_size} bytes)")

    if spec.sha256 is not None:
        got = sha256_file(dest_tmp)
        if got.lower() != spec.sha256.lower():
            raise RuntimeError(
                f"SHA256 mismatch:\n- url: {spec.url}\n- expected: {spec.sha256}\n- got: {got}"
            )

    os.replace(dest_tmp, spec.dest)
    dt = time.time() - t0
    sys.stderr.write(f"Downloaded {spec.dest} ({spec.dest.stat().st_size} bytes) in {dt:.1f}s\n")
    return spec.dest


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if orjson is not None:
                yield orjson.loads(line)
            else:
                yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("wb") as f:
        for r in rows:
            b = dumps_json(r)
            if not b.endswith(b"\n"):
                b += b"\n"
            f.write(b)

