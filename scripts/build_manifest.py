#!/usr/bin/env python3
"""
Emit manifests/latest.json — top 3 weeks (both tracks), consumed by the
lcchema-hub landing page via raw.githubusercontent.com.

Lives outside build_site.py because site/ is gitignored; the manifest needs
to be in a committed folder so raw.githubusercontent.com can serve it.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPORTS = ROOT / "reports"
MANIFESTS = ROOT / "manifests"
REPORT_BASE = "https://report.lcchema.cc"


def main():
    md_files = sorted(REPORTS.glob("*.md"))

    weeks_by_label: dict[str, dict] = {}
    for r in md_files:
        m = re.search(r"(\d{4})-W(\d{2})", r.stem)
        if not m:
            continue
        wl = f"{m.group(1)}-W{m.group(2)}"
        bucket = weeks_by_label.setdefault(wl, {"week": wl})
        if r.stem.startswith("malignant-"):
            bucket["malignant_url"] = f"{REPORT_BASE}/{r.stem}.html"
        elif r.stem.startswith("benign-"):
            bucket["benign_url"] = f"{REPORT_BASE}/{r.stem}.html"

    latest = sorted(weeks_by_label.values(), key=lambda w: w["week"], reverse=True)[:3]
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weeks":     latest,
    }

    MANIFESTS.mkdir(exist_ok=True)
    (MANIFESTS / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote manifests/latest.json: {len(latest)} weeks")


if __name__ == "__main__":
    main()
