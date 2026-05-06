#!/usr/bin/env python3
"""
Hematology Weekly Trend Tracker

Usage:
    python main.py scrape    [-m malignant|benign]  # scrape web news sources
    python main.py journals  [-m malignant|benign]  # fetch CrossRef journal articles
    python main.py report    [-m malignant|benign]  # generate weekly .md report
    python main.py run       [-m malignant|benign]  # scrape + journals + report
    python main.py fetch     [-m malignant|benign]  # fetch tweets (requires Twitter creds)
    python main.py discover  [-m malignant|benign]  # expand KOL list from recent mentions
    python main.py accounts                         # list tracked Twitter accounts
    python main.py setup                            # save Twitter cookies

Mode defaults to "malignant" if -m / --mode is not specified.
Reports are written to reports/<mode>-YYYY-WNN.md
"""

import os
import sys
from pathlib import Path

# -- Resolve mode BEFORE importing src so HEMA_MODE is set when config.py loads --
_mode = "malignant"
for _i, _a in enumerate(sys.argv):
    if _a in ("-m", "--mode") and _i + 1 < len(sys.argv):
        _mode = sys.argv[_i + 1]
        break
if _mode not in ("malignant", "benign"):
    print(f"Error: --mode must be 'malignant' or 'benign', got '{_mode}'", file=sys.stderr)
    sys.exit(1)
os.environ["HEMA_MODE"] = _mode
# ---------------------------------------------------------------------------------

from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from src import db, fetcher, discover, reporter, webscraper, crossref_fetcher

console = Console()
CREDS_FILE = Path(__file__).parent / "data" / ".creds"


def _load_creds() -> tuple[str, str, str, str] | None:
    if CREDS_FILE.exists():
        parts = CREDS_FILE.read_text().strip().splitlines()
        if len(parts) == 4:
            return parts[0], parts[1], parts[2], parts[3]
    return None


def _save_creds(username: str, email: str, auth_token: str, ct0: str):
    CREDS_FILE.parent.mkdir(exist_ok=True)
    CREDS_FILE.write_text(f"{username}\n{email}\n{auth_token}\n{ct0}", encoding="utf-8")
    CREDS_FILE.chmod(0o600)


def cmd_setup(username: str = None, email: str = None,
              auth_token: str = None, ct0: str = None):
    if not all([username, email, auth_token, ct0]):
        console.print("\n[bold cyan]Twitter Cookie Setup[/bold cyan]")
        console.print("Get auth_token and ct0 from browser DevTools -> Application -> Cookies -> x.com\n")
        username = input("Twitter username (without @): ").strip()
        email = input("Twitter email: ").strip()
        auth_token = input("auth_token cookie value: ").strip()
        ct0 = input("ct0 cookie value: ").strip()
    _save_creds(username, email, auth_token, ct0)
    console.print("[green]OK Credentials saved.[/green]")


def _require_creds() -> tuple[str, str, str, str]:
    creds = _load_creds()
    if creds:
        return creds
    console.print("[yellow]No credentials found. Running setup...[/yellow]\n")
    cmd_setup()
    return _load_creds()


def cmd_fetch():
    username, email, auth_token, ct0 = _require_creds()
    db.init_db()
    console.print(f"\n[bold]Fetching tweets (mode: {_mode})...[/bold]")
    fetcher.fetch(username, email, auth_token, ct0)
    console.print("[green]OK Fetch complete.[/green]")


def cmd_discover():
    db.init_db()
    tweets = db.get_tweets_since(days=7)
    console.print(f"\n[bold]Running KOL discovery on {len(tweets)} recent tweets...[/bold]")
    discover.discover_new_accounts(tweets, top_n=20)


def cmd_report(days: int = 7):
    db.init_db()
    console.print(f"\n[bold]Generating report (mode: {_mode}, last {days} days)...[/bold]")
    path = reporter.write_report(days=days)
    console.print(f"[green]OK Report written -> {path}[/green]")
    lines = path.read_text().splitlines()
    console.print("\n[dim]Preview:[/dim]\n")
    for line in lines[:40]:
        console.print(line)
    if len(lines) > 40:
        console.print(f"[dim]... ({len(lines) - 40} more lines)[/dim]")


def cmd_accounts():
    db.init_db()
    accounts = db.get_accounts()
    if not accounts:
        console.print("[yellow]No accounts tracked yet. Run: python main.py fetch[/yellow]")
        return
    t = Table(title=f"Tracked Accounts ({len(accounts)})")
    t.add_column("Handle", style="cyan")
    t.add_column("Name")
    t.add_column("Followers", justify="right")
    t.add_column("Source")
    for a in accounts[:30]:
        t.add_row(
            f"@{a['handle']}",
            a["display_name"] or "",
            f"{a['followers']:,}" if a["followers"] else "--",
            a["discovered_via"] or "seed",
        )
    console.print(t)


def cmd_scrape(days: int = 7):
    import asyncio, json
    console.print(f"\n[bold]Scraping web sources (mode: {_mode})...[/bold]")
    results = asyncio.run(webscraper.fetch_all(days=days))
    for source, articles in results.items():
        console.print(f"  [cyan]{source}[/cyan]: {len(articles)} articles found")
        for a in articles[:5]:
            console.print(f"    * {a.title[:80]}")
            if a.url:
                console.print(f"      {a.url}")

    out = Path(__file__).parent / "data" / f"webscrape_cache_{_mode}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {src: [{"title": a.title, "url": a.url, "source": a.source,
                "published": a.published, "summary": a.summary, "tags": a.tags}
               for a in arts]
         for src, arts in results.items()},
        ensure_ascii=False, indent=2
    ), encoding="utf-8")
    console.print(f"[green]OK Cached -> {out}[/green]")
    return results


def cmd_journals():
    import asyncio, json
    console.print(f"\n[bold]Fetching journal articles via CrossRef (mode: {_mode})...[/bold]")
    results = asyncio.run(crossref_fetcher.fetch_all())
    for journal, articles in results.items():
        console.print(f"  [cyan]{journal}[/cyan]: {len(articles)} articles")
        for a in articles[:4]:
            has_abs = "Y" if a.abstract_digest else "N"
            console.print(f"    [{has_abs}] {a.title[:75]}")
            console.print(f"        https://doi.org/{a.doi}")

    out = Path(__file__).parent / "data" / f"journals_cache_{_mode}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {jn: [{"title": a.title, "doi": a.doi, "journal": a.journal,
               "authors": a.authors, "published": a.published,
               "abstract": a.abstract, "abstract_digest": a.abstract_digest,
               "tags": a.tags, "url": a.url}
              for a in arts]
         for jn, arts in results.items()},
        ensure_ascii=False, indent=2
    ), encoding="utf-8")
    console.print(f"[green]OK Cached -> {out}[/green]")
    return results


def cmd_run():
    cmd_scrape()
    cmd_journals()
    cmd_report()


# Strip -m/--mode from argv before command dispatch
_clean_argv = [a for i, a in enumerate(sys.argv)
               if a not in ("-m", "--mode")
               and (i == 0 or sys.argv[i-1] not in ("-m", "--mode"))]

COMMANDS = {
    "setup": cmd_setup,
    "fetch": cmd_fetch,
    "discover": cmd_discover,
    "report": cmd_report,
    "scrape": cmd_scrape,
    "journals": cmd_journals,
    "accounts": cmd_accounts,
    "run": cmd_run,
}

if __name__ == "__main__":
    cmd = _clean_argv[1] if len(_clean_argv) > 1 else "run"
    if cmd not in COMMANDS:
        console.print(__doc__)
        sys.exit(1)
    COMMANDS[cmd]()
