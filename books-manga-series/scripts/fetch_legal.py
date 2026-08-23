#!/usr/bin/env python3
"""Download one legally offered ebook/comic and verify it is a real file.

Usage:
  python3 fetch_legal.py URL --out /path/to/file.epub
  python3 fetch_legal.py URL --out /path/to/file.pdf --min-bytes 20000

Exits 0 and prints JSON on success. Exits 2 on a bad/HTML payload.
Does not decide legality — the caller must only pass official URLs.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

BLOCK_HINTS = (
    "libgen",
    "library.lol",
    "z-lib",
    "zlib",
    "annas-archive",
    "sci-hub",
    "dokumen.pub",
    "pdfdrive",
    "mangadex",
    "mangakakalot",
    "manganato",
    "weebcentral",
    "hitomi.la",
    "comick.",
)

UA = "HermesLegalLibrary/1.0 (+https://hermes-agent.nousresearch.com)"


def die(msg: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": msg}), file=sys.stderr)
    raise SystemExit(code)


def looks_blocked(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in BLOCK_HINTS)


def sniff(data: bytes, dest_suffix: str) -> str | None:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK"):
        # EPUB is a zip that contains mimetype; CBZ/zip start the same
        if dest_suffix in {".epub", ".cbz", ".zip"}:
            return dest_suffix.lstrip(".")
        if b"mimetype" in data[:256] and b"epub" in data[:512].lower():
            return "epub"
        return "zip"
    if data[0:3] == b"\x1f\x8b":
        return "gz"
    return None


def fetch(url: str) -> bytes:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            ctype = (
                (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            )
            data = resp.read()
            final = resp.geturl()
    except urllib.error.HTTPError as e:
        die(f"HTTP {e.code} for {url}")
    except urllib.error.URLError as e:
        die(f"network error: {e.reason}")
    if "text/html" in ctype and not data.startswith((b"%PDF", b"PK")):
        die(f"got HTML landing page (content-type={ctype}) from {final}")
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--out", required=True)
    p.add_argument("--min-bytes", type=int, default=10_000)
    args = p.parse_args()

    if looks_blocked(args.url):
        die("refused: URL host is a known pirate/scanlation site")

    dest = Path(args.out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = fetch(args.url)
    if len(data) < args.min_bytes:
        die(f"file too small ({len(data)} bytes); probably not the ebook")

    kind = sniff(data, dest.suffix.lower())
    if kind is None:
        die(f"unrecognized file (magic={data[:24]!r})")

    dest.write_bytes(data)
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(dest.resolve()),
                "bytes": len(data),
                "kind": kind,
            }
        )
    )


if __name__ == "__main__":
    main()
