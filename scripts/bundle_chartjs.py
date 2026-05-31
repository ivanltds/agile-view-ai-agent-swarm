"""Download Chart.js and inline it into the report template for offline use.

Run locally before generating offline reports. The bundled output is written to
templates/report.offline.html.j2 and is intentionally not committed.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

CDN = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js"
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "templates" / "report.html.j2"
DST = ROOT / "templates" / "report.offline.html.j2"
TAG = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'


def main() -> int:
    print(f"Downloading {CDN} ...")
    js = urllib.request.urlopen(CDN, timeout=30).read().decode("utf-8")  # noqa: S310
    html = SRC.read_text(encoding="utf-8")
    html = html.replace(TAG, f"<script>{js}</script>")
    DST.write_text(html, encoding="utf-8")
    print(f"Wrote {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
