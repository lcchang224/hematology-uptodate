#!/usr/bin/env python3
"""
Weekly hematology report generator (no email).
Called by GitHub Actions every Friday 08:00 Taipei time (00:00 UTC Friday).
Published to report.lcchema.cc via CF Pages.

Usage:
  python scripts/generate_report.py              # both modes
  python scripts/generate_report.py malignant    # one mode only
"""
import json
import sys
from datetime import date
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
CLAUDE_MD = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

MODES = ("malignant", "benign")

SYSTEM_PROMPT = (
    "You are a senior hematologist writing structured weekly clinical update reports "
    "for fellow hematologists at NCKUH, Taiwan. Reports are precise and evidence-based, "
    "written in medical English. Include concrete numbers (HR, CI, p-value). "
    "Write clinical sections in paragraph prose, not bullet lists. "
    "CITATION FORMAT: never write full citations inline. Place a numbered footnote marker "
    "[^N] immediately after the claim (e.g., 'asciminib showed 95.2% MMR at Week 96[^1]'). "
    "Collect every reference in a single '## References' section at the very end of the "
    "report, one entry per line:\n"
    "[^1]: Author A et al. *Journal* Year. [DOI 10.xxx/yyy](https://doi.org/10.xxx/yyy)"
)


def week_label() -> str:
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def load_cache(mode: str) -> tuple[list, list]:
    j = DATA_DIR / f"journals_cache_{mode}.json"
    w = DATA_DIR / f"webscrape_cache_{mode}.json"

    def flatten(data):
        if isinstance(data, dict):
            result = []
            for v in data.values():
                result.extend(v if isinstance(v, list) else [v])
            return result
        return data if isinstance(data, list) else []

    journals = flatten(json.loads(j.read_text(encoding="utf-8"))) if j.exists() else []
    web = flatten(json.loads(w.read_text(encoding="utf-8"))) if w.exists() else []
    return journals, web


def previous_report_text(mode: str) -> str:
    reports = sorted(REPORTS_DIR.glob(f"{mode}-*.md"), reverse=True)
    wl = week_label()
    reports = [r for r in reports if wl not in r.name]
    return reports[0].read_text(encoding="utf-8")[:5000] if reports else ""


def build_prompt(mode: str, journals: list, web: list) -> str:
    wl = week_label()
    today = date.today().isoformat()
    label = "Hematological Malignancies" if mode == "malignant" else "Non-malignant Hematology"

    prev = previous_report_text(mode)
    prev_block = ""
    if prev:
        prev_block = (
            f"<previous_report>\n{prev}\n</previous_report>\n\n"
            "IMPORTANT: Do NOT repeat any finding already in the previous report with identical "
            "numbers. If a section has no genuinely new data this week, write "
            "`_No new signal this week_` and move on.\n\n"
        )

    return (
        f"Today is {today}. Generate the weekly hematology report for week {wl}.\n"
        f"Mode: {label}\n\n"
        f"{prev_block}"
        f"<instructions>\n{CLAUDE_MD}\n</instructions>\n\n"
        f"<journal_articles>\n{json.dumps(journals[:80], ensure_ascii=False)}\n</journal_articles>\n\n"
        f"<web_news>\n{json.dumps(web[:60], ensure_ascii=False)}\n</web_news>\n\n"
        f"Write the complete report following the structure for {label}. "
        "Use paragraph prose (not bullet lists) for all clinical sections."
    )


def call_claude(mode: str, journals: list, web: list) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(mode, journals, web)}],
    )
    return msg.content[0].text


def process(mode: str):
    print(f"\n=== {mode.upper()} ===")
    journals, web = load_cache(mode)
    print(f"  Cache: {len(journals)} journal articles, {len(web)} web items")

    if not journals and not web:
        print("  No data found — skipping report generation.")
        return

    print("  Calling Claude API...")
    report_md = call_claude(mode, journals, web)

    REPORTS_DIR.mkdir(exist_ok=True)
    wl = week_label()
    report_path = REPORTS_DIR / f"{mode}-{wl}.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"  Report saved: {report_path}")


if __name__ == "__main__":
    modes = sys.argv[1:] if len(sys.argv) > 1 else list(MODES)
    for m in modes:
        if m not in MODES:
            print(f"Unknown mode: {m}. Choose malignant or benign.")
            sys.exit(1)
        process(m)
    print("\nDone.")
