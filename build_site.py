"""Convert reports/*.md to a styled static site under site/, matching the email styling."""
import re
from datetime import date
from pathlib import Path
import markdown as md_lib

OUT = Path("site")
OUT.mkdir(exist_ok=True)

STYLES = {
    "malignant": {
        "label": "Hematological Malignancies",
        "primary": "#1a237e",
        "accent": "#b71c1c",
        "light_bg": "#e8eaf6",
    },
    "benign": {
        "label": "Non-malignant Hematology",
        "primary": "#1b5e20",
        "accent": "#e65100",
        "light_bg": "#e8f5e9",
    },
}

INDEX_PRIMARY = "#37474f"
INDEX_ACCENT  = "#00838f"
INDEX_BG      = "#eceff1"


def detect_mode(stem: str) -> str:
    if stem.startswith("malignant"): return "malignant"
    if stem.startswith("benign"):    return "benign"
    return "malignant"


def week_from_stem(stem: str) -> str:
    m = re.search(r"(\d{4})-W(\d{2})", stem)
    return f"{m.group(1)}-W{m.group(2)}" if m else stem


REPORT_CSS = """body{{margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#212121}}
.wrap{{max-width:740px;margin:0 auto;background:#fff}}
.nav{{padding:14px 32px;background:#fafafa;border-bottom:1px solid #e0e0e0;font-size:13px}}
.nav a{{color:{p};text-decoration:none}}.nav a:hover{{text-decoration:underline}}
.hdr{{background:{p};padding:28px 32px}}
.hdr h1{{margin:0;color:#fff;font-size:21px;font-weight:700;line-height:1.3}}
.hdr p{{margin:6px 0 0;color:rgba(255,255,255,.72);font-size:13px}}
.body{{padding:28px 32px;line-height:1.75;font-size:15px}}
h2{{color:{p};border-bottom:2px solid {a};padding-bottom:5px;margin-top:34px;font-size:17px}}
h3{{color:{p};font-size:15px;margin-top:22px}}
h4{{color:#424242;font-size:14px}}
p{{margin:0 0 12px}}
a{{color:{a};text-decoration:none}}a:hover{{text-decoration:underline}}
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
sup{{line-height:0}}sup a{{color:{a};font-weight:600;font-size:11px}}
.footnote{{border-top:2px solid #e0e0e0;margin-top:36px;padding-top:16px;font-size:13px;color:#616161;line-height:1.6}}
.footnote ol{{padding-left:20px;margin:8px 0 0}}
.footnote li{{margin-bottom:6px}}.footnote a{{color:{a}}}
.ftr{{background:{bg};padding:14px 32px;font-size:12px;color:#757575;border-top:1px solid #e0e0e0;line-height:1.6}}
@media(max-width:600px){{.nav,.hdr,.body,.ftr{{padding:18px 16px}}.hdr h1{{font-size:18px}}table{{font-size:12px}}td,th{{padding:5px 8px}}}}"""


def render_report(md_text: str, mode: str, wl: str) -> str:
    s = STYLES[mode]
    p, a, bg, label = s["primary"], s["accent"], s["light_bg"], s["label"]
    body = md_lib.markdown(md_text, extensions=["tables", "fenced_code", "footnotes"])
    css = REPORT_CSS.format(p=p, a=a, bg=bg)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hematology Weekly &mdash; {label} {wl}</title>
<style>{css}</style></head><body>
<div class="wrap">
<div class="nav"><a href="index.html">&larr; All reports</a></div>
<div class="hdr">
<h1>Hematology Weekly &mdash; {label}</h1>
<p>Week {wl} &nbsp;&middot;&nbsp; NCKUH Hematology Division</p>
</div>
<div class="body">
{body}
</div>
<div class="ftr">Auto-generated from CrossRef, ASH, EHA, ISTH, and OncLive sources. Verify clinical decisions against primary literature before acting.</div>
</div></body></html>"""


def render_index(malignant, benign, other) -> str:
    def by_year(reports):
        groups = {}
        for r in reports:
            m = re.search(r"(\d{4})-W(\d{2})", r.stem)
            if not m: continue
            groups.setdefault(m.group(1), []).append((m.group(2), r))
        return [(y, sorted(weeks, reverse=True)) for y, weeks in sorted(groups.items(), reverse=True)]

    def render_column(reports, title, primary, accent):
        years = by_year(reports)
        if not years:
            return f'<div class="col"><h2 style="color:{primary};border-bottom-color:{accent}">{title}</h2><p><em>None yet</em></p></div>'
        current_year = years[0][0]
        blocks = []
        for year, weeks in years:
            is_open = " open" if year == current_year else ""
            items = "\n".join(
                f'<li><a href="{r.stem}.html" style="color:{accent}">W{week}</a></li>'
                for week, r in weeks
            )
            blocks.append(
                f'<details{is_open}><summary style="color:{primary}">{year} ({len(weeks)})</summary>'
                f'<ul class="weeks">{items}</ul></details>'
            )
        return (f'<div class="col"><h2 style="color:{primary};border-bottom-color:{accent}">{title}</h2>'
                f'{"".join(blocks)}</div>')

    mal_col = render_column(malignant, "Malignant",
                            STYLES["malignant"]["primary"], STYLES["malignant"]["accent"])
    ben_col = render_column(benign, "Benign",
                            STYLES["benign"]["primary"], STYLES["benign"]["accent"])

    extra_css = """
.cols{display:flex;gap:32px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
.col h2{border-bottom:2px solid;padding-bottom:5px;margin-top:0}
details{margin:8px 0}
summary{cursor:pointer;font-weight:600;padding:6px 0;font-size:15px;user-select:none}
summary:hover{opacity:.75}
.weeks{list-style:none;padding:0;margin:6px 0 12px 16px}
.weeks li{margin:4px 0;font-size:14px}
.other{margin-top:32px;padding-top:16px;border-top:1px solid #e0e0e0}
@media(max-width:680px){.cols{flex-direction:column;gap:0}}"""

    css = REPORT_CSS.format(p=INDEX_PRIMARY, a=INDEX_ACCENT, bg=INDEX_BG) + extra_css

    other_section = ""
    if other:
        items = "\n".join(f'<li><a href="{r.stem}.html">{r.stem}</a></li>'
                          for r in sorted(other, reverse=True))
        other_section = f'<div class="other"><h3>Other</h3><ul class="weeks">{items}</ul></div>'

    today = date.today().isoformat()
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hematology Weekly Reports</title>
<style>{css}</style></head><body>
<div class="wrap">
<div class="hdr">
<h1>Hematology Weekly Reports</h1>
<p>NCKUH Hematology Division &nbsp;&middot;&nbsp; Updated {today}</p>
</div>
<div class="body">
<div class="cols">{mal_col}{ben_col}</div>
{other_section}
</div>
<div class="ftr">Auto-generated weekly. Sources: CrossRef, ASH, EHA, ISTH, OncLive.</div>
</div></body></html>"""


reports = sorted(Path("reports").glob("*.md"))
for r in reports:
    mode = detect_mode(r.stem)
    wl = week_from_stem(r.stem)
    (OUT / f"{r.stem}.html").write_text(
        render_report(r.read_text(encoding="utf-8"), mode, wl), encoding="utf-8"
    )

malignant = sorted([r for r in reports if r.stem.startswith("malignant-")], reverse=True)
benign    = sorted([r for r in reports if r.stem.startswith("benign-")], reverse=True)
other     = [r for r in reports if not (r.stem.startswith("malignant-") or r.stem.startswith("benign-"))]

(OUT / "index.html").write_text(render_index(malignant, benign, other), encoding="utf-8")
print(f"Built {len(reports)} reports + index")
