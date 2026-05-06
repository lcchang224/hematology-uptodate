# CLAUDE.md — Hematology Weekly Report (Dual-Mode)

## Project Purpose

Auto-generate weekly Markdown reports on hematology trends from:
- CrossRef API (via `python main.py journals -m <mode>`)
- Web news (OncDaily RSS, OncLive/ASH/EHA/ESMO via Google News RSS)
- PubMed MCP (`mcp__claude_ai_PubMed__search_articles`) — if available
- ClinicalTrials.gov MCP — if available

Two independent report modes:
| Mode | Command flag | Report prefix | Disease scope |
|------|-------------|---------------|---------------|
| Hematological Malignancies | `-m malignant` | `malignant-YYYY-WNN.md` | AML, ALL, CML, CLL, MDS, MPN, all lymphomas, myeloma, transplant |
| Non-malignant Hematology | `-m benign` | `benign-YYYY-WNN.md` | ITP, TTP, PNH, aplastic anemia, hemophilia, thalassemia, AIHA, coagulation |

---

## Before Writing a New Report

**MANDATORY — do this BEFORE writing a single word of content:**

```bash
# Find the latest report for this mode
PREV=$(ls reports/ -t | grep "^malignant-" | head -1)   # or grep "^benign-"
echo "Previous report: $PREV"

# Read it fully — note every trial, drug, and section covered
# Grep key terms to see what's already documented
```

After reading the previous report, answer these before writing:
- Which trials were already covered with final/mature data? → **skip entirely**
- Which had interim data last week? → include only if new follow-up published
- Which approvals were already documented? → **skip unless indication expanded**

**Do NOT repeat** any finding with identical numbers. If new data: state explicitly what changed vs last week.

If a section has no genuinely new data this week: write `_No new signal this week_` and move on.

---

## Running the Pipeline

```bash
# Hematological malignancies
uv run python main.py scrape   -m malignant   # scrape OncDaily, OncLive, ASH, EHA
uv run python main.py journals -m malignant   # fetch CrossRef articles
uv run python main.py run      -m malignant   # all of the above + report

# Non-malignant hematology
uv run python main.py scrape   -m benign
uv run python main.py journals -m benign
uv run python main.py run      -m benign
```

Cached data:
- `data/webscrape_cache_malignant.json` / `data/webscrape_cache_benign.json`
- `data/journals_cache_malignant.json` / `data/journals_cache_benign.json`

**CrossRef filtering note:** The fetcher applies a keyword pre-screen (broad net). When writing
the report, read the cache and **filter in-session** — discard articles whose primary topic is
not hematology-relevant. Only include confirmed relevant articles in the Journal Literature section.

---

## Report File Naming

```
reports/malignant-YYYY-WNN.md
reports/benign-YYYY-WNN.md
```

ISO week: `python3 -c "from datetime import date; d=date.today(); print(f'{d.year}-W{d.isocalendar()[1]:02d}')"`

---

## Report Structure — Hematological Malignancies (`malignant-YYYY-WNN.md`)

```
# Hematology (Malignant) Weekly Report — YYYY-WNN

> Generated: YYYY-MM-DD | Sources: CrossRef, OncDaily, OncLive, ASH News
> Coverage: past 7–14 days | Active Phase III trials tracked: N

---

## Summary
(Top 5 signals this week — concrete numbers, trial names)

## I. AML — Acute Myeloid Leukemia
## II. ALL — Acute Lymphoblastic Leukemia
## III. CML — Chronic Myeloid Leukemia
## IV. CLL / SLL — Chronic Lymphocytic Leukemia
## V. MDS — Myelodysplastic Syndromes
## VI. MPN — Myeloproliferative Neoplasms (PV / ET / MF)
## VII. DLBCL & Aggressive B-cell Lymphoma
## VIII. Indolent Lymphoma (FL, MCL, MZL)
## IX. Hodgkin Lymphoma & T-cell Lymphoma
## X. NK/T-cell Lymphoma (Asia focus)
## XI. Multiple Myeloma
## XII. Transplant & Cellular Therapy (CAR-T / HSCT / GVHD)
## XIII. Active High-Priority Trials — Tracker
## XIV. Taiwan Clinical Context
## XV. Key Takeaways

## XVI. Media Digest
(OncDaily / OncLive / ASH / EHA news table)

## Journal Literature — CrossRef
(keyword-filtered articles from Blood, Leukemia, Haematologica, etc.)
```

---

## Report Structure — Non-malignant Hematology (`benign-YYYY-WNN.md`)

```
# Hematology (Non-malignant) Weekly Report — YYYY-WNN

> Generated: YYYY-MM-DD | Sources: CrossRef, ASH News, ISTH, EHA
> Coverage: past 7–14 days

---

## Summary
(Top 5 signals this week)

## I. Immune Thrombocytopenia (ITP)
## II. TTP / HUS / Thrombotic Microangiopathy
## III. Aplastic Anemia
## IV. PNH — Paroxysmal Nocturnal Hemoglobinuria
## V. Hemophilia A & B (including gene therapy)
## VI. Von Willebrand Disease
## VII. Thalassemia (alpha & beta; Taiwan-relevant)
## VIII. Autoimmune Hemolytic Anemia (AIHA)
## IX. Red Cell Disorders (G6PD, PK deficiency, hereditary spherocytosis)
## X. Iron Deficiency & Nutritional Anemias
## XI. Thrombosis & Coagulation (VTE, APS, inherited thrombophilia)
## XII. Active High-Priority Trials — Tracker
## XIII. Taiwan Clinical Context
## XIV. Key Takeaways

## XV. Media Digest

## Journal Literature — CrossRef
(Blood, BJH, Haematologica, AJH, JTH)
```

---

## Writing Style

- Language: **English** — medical terms stay as-is (HR, PFS, ADAMTS13, etc.)
- Every clinical claim must be cited. Use numbered footnote markers **only** — never write full citations inline. Place `[^N]` immediately after the claim. Collect all references in a single `## References` section at the very end of the report:
  `[^1]: Author A et al. *Journal* Year. [DOI 10.xxx/yyy](https://doi.org/10.xxx/yyy)`
- Tables: use Markdown tables for comparative data (treatment vs control arm)
- Numbers: always include HR, CI, p-value when available
- Avoid vague superlatives — every "significant" needs a number
- Sections without new data this week: write `_No new signal this week_`

---

## Taiwan Clinical Context Section

Always add a brief Taiwan-specific note for each report:
- **Malignant**: drug availability in Taiwan (NHI coverage), relevant trial sites (NTUH, VGH, CGMH, CMUH), and disease patterns (e.g., NK/T-cell lymphoma is more prevalent in Asia)
- **Benign**: thalassemia carrier prevalence in Taiwan (~4–5% alpha, ~1–2% beta), G6PD deficiency rates, NHI coverage for novel agents (eltrombopag, eculizumab, emicizumab)

---

## Maintenance

| Problem | Fix |
|---------|-----|
| New drug not captured | Add to `source/<mode>/keywords.yml` and `drug_groups.yml` |
| New journal | Add to `source/<mode>/journals.yml` |
| New web source | Add to `source/<mode>/web_sources.yml` |
| Twitter op_id 404 | Update `source/<mode>/twitter.yml` `op_id` |
| Google News returns 0 results | Adjust `query` field in `web_sources.yml` |

---

## After Writing

1. Check word count: aim for 2000–6000 words per report
2. Verify all Markdown tables have header separators (`|---|---|`)
3. Commit: `git add reports/<mode>-YYYY-WNN.md && git commit -m "report: <mode> YYYY-WNN"`
4. Push → GitHub Action auto-publishes to Wiki

---

## Switching / Adding Disease Areas

This system is **disease-agnostic**. To add a new focus area (e.g., pediatric hematology):
1. Create `source/<newmode>/` with all 5 YAML files + `twitter.yml` + `seeds.txt`
2. Run with `HEMA_MODE=<newmode>` or `-m <newmode>`
3. Add the new mode name to the validation list in `main.py`
