"""Convert reports/*.md to a static HTML site under site/, with an index."""
from pathlib import Path
import markdown

OUT = Path("site")
OUT.mkdir(exist_ok=True)

CSS = """body{font-family:-apple-system,sans-serif;max-width:780px;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.6}
h1,h2,h3{line-height:1.2}h1{border-bottom:1px solid #eee;padding-bottom:.3rem}
code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px;font-size:.9em}
pre{background:#f4f4f4;padding:1rem;overflow-x:auto;border-radius:5px}
table{border-collapse:collapse;margin:1rem 0;width:100%}
th,td{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}
th{background:#f9f9f9}
a{color:#0066cc;text-decoration:none}a:hover{text-decoration:underline}
blockquote{border-left:3px solid #ccc;padding-left:1rem;color:#666;margin:1rem 0}
.nav{margin-bottom:1.5rem;color:#666}"""

def wrap(title, body, is_index=False):
    nav = "" if is_index else '<div class="nav"><a href="index.html">&larr; All reports</a></div>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style></head><body>
{nav}
{body}
</body></html>"""

md = markdown.Markdown(extensions=["tables", "fenced_code", "footnotes", "toc"])
reports = sorted(Path("reports").glob("*.md"))

for r in reports:
    html = md.reset().convert(r.read_text(encoding="utf-8"))
    (OUT / f"{r.stem}.html").write_text(wrap(r.stem, html), encoding="utf-8")

malignant = sorted([r for r in reports if r.stem.startswith("malignant-")], reverse=True)
benign    = sorted([r for r in reports if r.stem.startswith("benign-")], reverse=True)
other     = [r for r in reports if not (r.stem.startswith("malignant-") or r.stem.startswith("benign-"))]

def lis(items):
    if not items: return "<li><em>None yet</em></li>"
    return "\n".join(f'<li><a href="{r.stem}.html">{r.stem}</a></li>' for r in items)

body = f"""<h1>Hematology Weekly Reports</h1>
<h2>Hematological Malignancies</h2><ul>{lis(malignant)}</ul>
<h2>Non-malignant Hematology</h2><ul>{lis(benign)}</ul>"""
if other:
    body += f'\n<h2>Other</h2><ul>{lis(sorted(other, reverse=True))}</ul>'

(OUT / "index.html").write_text(wrap("Hematology Weekly Reports", body, is_index=True), encoding="utf-8")
print(f"Built {len(reports)} reports + index")
