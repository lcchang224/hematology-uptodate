#!/usr/bin/env python3
"""
Weekly hematology report generator + emailer.
Called by GitHub Actions every Friday 08:00 Taipei time (00:00 UTC Friday).

Usage:
  python scripts/generate_and_email.py              # both modes
  python scripts/generate_and_email.py malignant    # one mode only
"""
import json
import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import markdown as md_lib

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
CLAUDE_MD = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

STYLES = {
    "malignant": {
        "label": "Hematological Malignancies",
        "primary": "#1a237e",   # navy
        "accent": "#b71c1c",    # crimson
        "light_bg": "#e8eaf6",  # light indigo
    },
    "benign": {
        "label": "Non-malignant Hematology",
        "primary": "#1b5e20",   # forest green
        "accent": "#e65100",    # deep amber
        "light_bg": "#e8f5e9",  # light green
    },
}

SYSTEM_PROMPT = (
    "You are a senior hematologist writing structured weekly clinical update reports "
    "for fellow hematologists at NCKUH, Taiwan. Reports are precise and evidence-based, "
    "written in medical English. Cite trial names, authors, journal, DOI. Include concrete "
    "numbers (HR, CI, p-value). Write clinical sections in paragraph prose, not bullet lists."
)


def week_label() -> str:
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def load_cache(mode: str) -> tuple[list, list]:
    j = DATA_DIR / f"journals_cache_{mode}.json"
    w = DATA_DIR / f"webscrape_cache_{mode}.json"
    journals = json.loads(j.read_text(encoding="utf-8")) if j.exists() else []
    web = json.loads(w.read_text(encoding="utf-8")) if w.exists() else []
    return journals, web


def previous_report_text(mode: str) -> str:
    reports = sorted(REPORTS_DIR.glob(f"{mode}-*.md"), reverse=True)
    # Skip current week's report if it already exists
    wl = week_label()
    reports = [r for r in reports if wl not in r.name]
    return reports[0].read_text(encoding="utf-8")[:5000] if reports else ""


def build_prompt(mode: str, journals: list, web: list) -> str:
    wl = week_label()
    today = date.today().isoformat()
    label = STYLES[mode]["label"]

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


def to_html(md_text: str, mode: str) -> str:
    s = STYLES[mode]
    p, a, bg, label = s["primary"], s["accent"], s["light_bg"], s["label"]
    body = md_lib.markdown(md_text, extensions=["tables", "fenced_code"])
    wl = week_label()
    today = date.today().isoformat()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hematology Weekly &mdash; {label} {wl}</title>
<style>
body{{margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#212121}}
.wrap{{max-width:740px;margin:0 auto;background:#fff}}
.hdr{{background:{p};padding:28px 32px}}
.hdr h1{{margin:0;color:#fff;font-size:21px;font-weight:700;line-height:1.3}}
.hdr p{{margin:6px 0 0;color:rgba(255,255,255,.72);font-size:13px}}
.body{{padding:28px 32px;line-height:1.75;font-size:15px}}
h2{{color:{p};border-bottom:2px solid {a};padding-bottom:5px;margin-top:34px;font-size:17px}}
h3{{color:{p};font-size:15px;margin-top:22px}}
h4{{color:#424242;font-size:14px}}
p{{margin:0 0 12px}}
a{{color:{a};text-decoration:none}}
a:hover{{text-decoration:underline}}
table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}}
th{{background:{p};color:#fff;padding:8px 12px;text-align:left;font-weight:600}}
td{{padding:7px 12px;border-bottom:1px solid #e0e0e0;vertical-align:top}}
tr:nth-child(even) td{{background:{bg}}}
blockquote{{border-left:4px solid {a};margin:14px 0;padding:10px 16px;background:{bg};color:#424242;border-radius:0 4px 4px 0}}
code{{background:#f5f5f5;padding:2px 5px;border-radius:3px;font-family:'Courier New',monospace;font-size:13px}}
pre{{background:#f5f5f5;padding:14px;border-radius:4px;overflow-x:auto}}
pre code{{background:none;padding:0}}
em{{color:#616161}}
strong{{color:#212121}}
.ftr{{background:{bg};padding:14px 32px;font-size:12px;color:#757575;border-top:1px solid #e0e0e0;line-height:1.6}}
@media(max-width:600px){{
  .hdr,.body,.ftr{{padding:18px 16px}}
  .hdr h1{{font-size:18px}}
  table{{font-size:12px}}
  td,th{{padding:5px 8px}}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>Hematology Weekly &mdash; {label}</h1>
    <p>Week {wl} &nbsp;&middot;&nbsp; {today} &nbsp;&middot;&nbsp; NCKUH Hematology Division</p>
  </div>
  <div class="body">
{body}
  </div>
  <div class="ftr">
    Auto-generated from CrossRef, ASH, EHA, ISTH, and OncLive sources.
    Verify clinical decisions against primary literature before acting.
  </div>
</div>
</body>
</html>"""


def send_email(subject: str, html: str):
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Hematology Weekly <{user}>"
    msg["To"] = user
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(user, pw)
        srv.sendmail(user, user, msg.as_string())
    print(f"  Email sent -> {user}")


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

    html = to_html(report_md, mode)
    label = STYLES[mode]["label"]
    send_email(f"[Hematology Weekly] {label} — {wl}", html)


if __name__ == "__main__":
    modes = sys.argv[1:] if len(sys.argv) > 1 else ["malignant", "benign"]
    for m in modes:
        if m not in STYLES:
            print(f"Unknown mode: {m}. Choose malignant or benign.")
            sys.exit(1)
        process(m)
    print("\nDone.")
