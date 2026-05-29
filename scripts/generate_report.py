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
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

MARKER_RE = re.compile(r"\[\^([0-9]+)\](?!:)")  # [^N] not followed by colon
DEF_RE    = re.compile(r"^\[\^([0-9]+)\]:", re.MULTILINE)
REFS_HEADER_RE = re.compile(r"^##\s+References\s*$", re.MULTILINE)


def footnote_gap(md_text: str) -> tuple[set[str], set[str], bool]:
    """Return (markers_without_defs, defs_without_markers, has_refs_header)."""
    markers = set(MARKER_RE.findall(md_text))
    defs    = set(DEF_RE.findall(md_text))
    return (markers - defs, defs - markers, bool(REFS_HEADER_RE.search(md_text)))

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
    user_msg = build_prompt(mode, journals, web)
    messages = [{"role": "user", "content": user_msg}]

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    report = msg.content[0].text

    missing, _, has_header = footnote_gap(report)
    if not missing and has_header:
        return report

    # One follow-up turn to repair the References section.
    print(f"  ! Footnote check failed (missing={len(missing)}, has_header={has_header}) — requesting repair.")
    messages.append({"role": "assistant", "content": report})
    messages.append({"role": "user", "content": (
        "The report is missing a complete `## References` section. "
        f"Every `[^N]` marker in the prose must have a matching `[^N]: …` definition line. "
        f"Missing definitions for markers: {sorted(missing, key=int) if missing else 'none'}. "
        f"References header present: {has_header}. "
        "Output the FULL corrected report from the title down, including a `## References` section "
        "at the very end with one `[^N]: Author A et al. *Journal* Year. [DOI 10.xxx/yyy](https://doi.org/10.xxx/yyy)` "
        "line per marker. Use the DOIs from the <journal_articles> block I gave you earlier."
    )})

    msg2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    repaired = msg2.content[0].text

    missing2, _, has_header2 = footnote_gap(repaired)
    if missing2 or not has_header2:
        raise RuntimeError(
            f"Footnote repair failed for {mode}: still missing {sorted(missing2, key=int)}, "
            f"has_header={has_header2}. Aborting so the workflow fails loud."
        )
    print(f"  ✓ Footnote repair succeeded.")
    return repaired


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
