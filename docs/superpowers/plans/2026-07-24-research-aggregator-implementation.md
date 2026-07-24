# Research Paper Aggregator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily-refreshed research-paper digest: a Claude Artifact website showing Lucas's curated picks, fed by a locally-scheduled Claude agent that researches, validates, and publishes 10 new papers a day, backed by a GitHub repo as the data store.

**Architecture:** Static site (single HTML file with embedded JSON data, rendered client-side in vanilla JS) generated from `data/papers.json` by a small Python build script, republished as a Claude Artifact. A scheduled task (Claude Code Desktop's local scheduler — confirmed 2026-07-24 to run only while the app is open, not a true cloud service) executes a self-contained research prompt daily, commits new data to GitHub, rebuilds the site, and republishes.

**Tech Stack:** Python 3 + pytest (data validation, site build script — no other dependencies needed), vanilla HTML/CSS/JS (no framework, no bundler — keeps the Artifact self-contained per its CSP), git + GitHub CLI (`gh`) for the data-store repo.

## Global Constraints

- 10 new papers per day; at least 1 each from `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`; remaining 6 from any of the 8 tracked categories.
- Search year-descending from 2026 down to 2019 per category; prefer newest, but don't force a weak pick just to stay recent.
- Every paper needs all of: title, link, summary, journal, year, category, date_surfaced, retraction_status, citation_count + source + checked date, contradicting_papers (0-5 items, each with title+link, never fabricated).
- No paper already present in `data/papers.json` (by `id`) may be re-selected.
- The Artifact must always be republished to the exact same `file_path` so its URL never changes.
- No framework/bundler — the published page is a single self-contained HTML file (Artifact CSP blocks external requests).
- **Working directory:** every command in every task assumes the current directory is the repo root, `C:\Users\Lucas\Desktop\claude code\research-aggregator`, unless a step says otherwise.

---

## File Structure

```
research-aggregator/
  data/
    papers.json                  # [] initially; the full history of surfaced papers
    SCHEMA.md                    # human-readable field reference for the daily agent
  scripts/
    __init__.py
    validate_papers.py           # validate_paper(), validate_papers(), CATEGORIES, REQUIRED_QUOTA_CATEGORIES
    site_data.py                 # group_by_date(), latest_date(), category_counts()
    build_site.py                # render_html(), build() -> writes site/dist/index.html
  site/
    artifact_template.html       # the actual page design (magazine feed, tabs, chips, marks)
    dist/
      index.html                 # generated output, gitignored
  agent/
    research_prompt.md           # canonical, self-contained daily research-agent prompt
  tests/
    test_validate_papers.py
    test_site_data.py
    test_build_site.py
  docs/superpowers/
    specs/2026-07-24-research-aggregator-design.md   # already exists
    plans/2026-07-24-research-aggregator-implementation.md   # this file
  README.md
  .gitignore
```

---

### Task 1: GitHub repo setup

**Files:**
- Modify: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Produces: a GitHub remote named `origin` on branch `master`, pushed and up to date. All later tasks assume `git push` works without further auth setup.

- [ ] **Step 1: Check for GitHub CLI**

Run: `gh --version`

If it prints a version, skip to Step 3. If it errors with "command not found" (confirmed missing as of 2026-07-24), continue to Step 2.

- [ ] **Step 2: Install GitHub CLI (USER ACTION — requires approval to run, and interactive auth after)**

Run:
```bash
winget install --id GitHub.cli
```

Then, in a **new** terminal (so PATH picks up the install), Lucas runs this himself interactively — it opens a browser for GitHub login and cannot be done by the agent:
```bash
gh auth login
```
Choose: GitHub.com → HTTPS → "Login with a web browser" → follow the prompt.

- [ ] **Step 3: Verify auth**

Run: `gh auth status`
Expected: output showing "Logged in to github.com as <username>"

- [ ] **Step 4: Update .gitignore**

Add Python/build artifacts to the existing file:

```
.superpowers/
.venv/
__pycache__/
*.pyc
site/dist/
```

- [ ] **Step 5: Write README.md**

```markdown
# Research Digest

A daily-refreshed feed of groundbreaking biomedical/neuroscience research papers,
curated for video research. See `docs/superpowers/specs/2026-07-24-research-aggregator-design.md`
for the full design.

## Layout
- `data/papers.json` — full history of every paper ever surfaced (source of truth)
- `scripts/` — validation and site-build logic (Python, tested with pytest)
- `site/artifact_template.html` — the page design; `site/dist/index.html` is generated, not edited directly
- `agent/research_prompt.md` — the self-contained prompt the daily scheduled task runs

## Rebuilding the site locally

    python -m scripts.build_site

Writes `site/dist/index.html`, which then gets published via the Artifact tool.

## Running tests

    python -m pytest tests/ -v
```

- [ ] **Step 6: Commit gitignore/README changes**

```bash
git add .gitignore README.md
git commit -m "Add README and expand .gitignore for Python build artifacts"
```

- [ ] **Step 7: Create the GitHub repo and push**

```bash
gh repo create research-aggregator --private --source=. --remote=origin
git push -u origin master
```

- [ ] **Step 8: Verify the push**

Run: `git ls-remote origin`
Expected: at least one line of output referencing `refs/heads/master` (confirms the remote has the commits).

---

### Task 2: Data schema and validation (TDD)

**Files:**
- Create: `data/papers.json`
- Create: `data/SCHEMA.md`
- Create: `scripts/__init__.py`
- Create: `scripts/validate_papers.py`
- Test: `tests/__init__.py`
- Test: `tests/test_validate_papers.py`

**Interfaces:**
- Produces: `validate_paper(paper: dict) -> list[str]`, `validate_papers(papers: list[dict]) -> list[str]`, `CATEGORIES: set[str]`, `REQUIRED_QUOTA_CATEGORIES: set[str]` — all imported by `scripts/build_site.py` (Task 4) and referenced by `agent/research_prompt.md` (Task 6).

- [ ] **Step 1: Set up a virtualenv and install pytest**

```bash
python -m venv .venv
.venv\Scripts\python -m pip install pytest
```

- [ ] **Step 2: Create empty data file and package markers**

`data/papers.json`:
```json
[]
```

`scripts/__init__.py`: (empty file)

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Write data/SCHEMA.md**

```markdown
# papers.json field reference

Each entry in `data/papers.json` is an object with these fields:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique slug, e.g. `nature-2024-alphafold3`. Must be unique across the whole file. |
| `title` | string | Paper title. |
| `link` | string | Direct URL, `http(s)://` — prefer publisher/PubMed/PMC over paywalled aggregators. |
| `summary` | string | 2-4 sentences, smart-layperson audience. |
| `journal` | string | Journal/venue name. |
| `year` | int | Year published. |
| `category` | string | One of: `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`, `ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`. |
| `date_surfaced` | string | ISO date `YYYY-MM-DD` — the day this paper appeared in the digest. |
| `retraction_status` | string | Explicit statement of what was checked and found, even if "none found." Never omit. |
| `citation_count` | int | Non-negative. |
| `citation_source` | string | e.g. "Semantic Scholar". |
| `citation_checked_date` | string | ISO date `YYYY-MM-DD`. |
| `contradicting_papers` | list | 0-5 items, each `{"title": str, "link": str}`. Empty list if none genuinely exist — never fabricate one. |

Quota categories (at least 1 each required per day): `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`.
```

- [ ] **Step 4: Write the failing tests**

`tests/test_validate_papers.py`:
```python
from scripts.validate_papers import validate_paper, validate_papers, CATEGORIES, REQUIRED_QUOTA_CATEGORIES


def make_valid_paper(**overrides):
    paper = {
        "id": "nature-2024-alphafold3",
        "title": "Accurate structure prediction of biomolecular interactions with AlphaFold 3",
        "link": "https://www.nature.com/articles/s41586-024-07487-w",
        "summary": "DeepMind's successor to AlphaFold2 predicts structures of complexes involving proteins, DNA, RNA, and small molecules.",
        "journal": "Nature",
        "year": 2024,
        "category": "ai_biology",
        "date_surfaced": "2026-07-25",
        "retraction_status": "No retraction or correction found (checked Retraction Watch, PubPeer -- 2026-07-24).",
        "citation_count": 12392,
        "citation_source": "Semantic Scholar",
        "citation_checked_date": "2026-07-24",
        "contradicting_papers": [
            {"title": "A comprehensive benchmarking of AlphaFold3", "link": "https://academic.oup.com/bib/article/26/6/bbaf616/8351050"}
        ],
    }
    paper.update(overrides)
    return paper


def test_valid_paper_has_no_errors():
    assert validate_paper(make_valid_paper()) == []


def test_missing_title_is_an_error():
    paper = make_valid_paper()
    del paper["title"]
    errors = validate_paper(paper)
    assert any("title" in e for e in errors)


def test_invalid_category_is_an_error():
    paper = make_valid_paper(category="cardiology")
    errors = validate_paper(paper)
    assert any("category" in e for e in errors)


def test_too_many_contradicting_papers_is_an_error():
    paper = make_valid_paper(contradicting_papers=[{"title": f"P{i}", "link": "https://example.com"} for i in range(6)])
    errors = validate_paper(paper)
    assert any("contradicting_papers" in e for e in errors)


def test_zero_contradicting_papers_is_valid():
    paper = make_valid_paper(contradicting_papers=[])
    assert validate_paper(paper) == []


def test_bad_date_format_is_an_error():
    paper = make_valid_paper(date_surfaced="07/25/2026")
    errors = validate_paper(paper)
    assert any("date_surfaced" in e for e in errors)


def test_negative_citation_count_is_an_error():
    paper = make_valid_paper(citation_count=-1)
    errors = validate_paper(paper)
    assert any("citation_count" in e for e in errors)


def test_duplicate_ids_across_list_is_an_error():
    p1 = make_valid_paper()
    p2 = make_valid_paper()
    errors = validate_papers([p1, p2])
    assert any("duplicate" in e.lower() for e in errors)


def test_required_quota_categories_are_a_subset_of_categories():
    assert REQUIRED_QUOTA_CATEGORIES <= CATEGORIES
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_validate_papers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.validate_papers'`

- [ ] **Step 6: Implement scripts/validate_papers.py**

```python
import re
import sys
import json

CATEGORIES = {
    "cell_therapy",
    "regenerative_medicine",
    "clinical_trial",
    "neuroscience",
    "ai_biology",
    "biomedical_devices",
    "tissue_engineering",
    "gene_therapy",
}

REQUIRED_QUOTA_CATEGORIES = {"cell_therapy", "regenerative_medicine", "clinical_trial", "neuroscience"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED_STRING_FIELDS = ["id", "title", "link", "summary", "journal", "retraction_status", "citation_source"]


def validate_paper(paper):
    errors = []
    paper_id = paper.get("id", "<no id>")

    for field in _REQUIRED_STRING_FIELDS:
        value = paper.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{paper_id}: '{field}' must be a non-empty string")

    link = paper.get("link")
    if isinstance(link, str) and not (link.startswith("http://") or link.startswith("https://")):
        errors.append(f"{paper_id}: 'link' must be an http(s) URL")

    year = paper.get("year")
    if not isinstance(year, int) or isinstance(year, bool) or not (1900 <= year <= 2100):
        errors.append(f"{paper_id}: 'year' must be an int between 1900 and 2100")

    category = paper.get("category")
    if category not in CATEGORIES:
        errors.append(f"{paper_id}: 'category' must be one of {sorted(CATEGORIES)}, got {category!r}")

    for date_field in ("date_surfaced", "citation_checked_date"):
        value = paper.get(date_field)
        if not isinstance(value, str) or not _DATE_RE.match(value):
            errors.append(f"{paper_id}: '{date_field}' must be an ISO date string YYYY-MM-DD")

    citation_count = paper.get("citation_count")
    if not isinstance(citation_count, int) or isinstance(citation_count, bool) or citation_count < 0:
        errors.append(f"{paper_id}: 'citation_count' must be a non-negative int")

    contradicting = paper.get("contradicting_papers")
    if not isinstance(contradicting, list) or len(contradicting) > 5:
        errors.append(f"{paper_id}: 'contradicting_papers' must be a list of 0-5 items")
    else:
        for i, item in enumerate(contradicting):
            if not isinstance(item, dict) or not item.get("title") or not item.get("link"):
                errors.append(f"{paper_id}: 'contradicting_papers[{i}]' must have non-empty 'title' and 'link'")

    return errors


def validate_papers(papers):
    errors = []
    seen_ids = {}
    for paper in papers:
        errors.extend(validate_paper(paper))
        paper_id = paper.get("id")
        if paper_id:
            seen_ids[paper_id] = seen_ids.get(paper_id, 0) + 1
    for paper_id, count in seen_ids.items():
        if count > 1:
            errors.append(f"duplicate id '{paper_id}' appears {count} times")
    return errors


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/papers.json"
    with open(path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    problems = validate_papers(papers)
    if problems:
        for problem in problems:
            print(problem)
        sys.exit(1)
    print(f"OK: {len(papers)} papers valid")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_validate_papers.py -v`
Expected: all 8 tests PASS

- [ ] **Step 8: Commit**

```bash
git add data/papers.json data/SCHEMA.md scripts/__init__.py scripts/validate_papers.py tests/__init__.py tests/test_validate_papers.py
git commit -m "Add papers.json schema and validation logic with tests"
git push
```

---

### Task 3: Date-grouping helpers (TDD)

**Files:**
- Create: `scripts/site_data.py`
- Test: `tests/test_site_data.py`

**Interfaces:**
- Consumes: nothing (pure functions over plain dicts/lists).
- Produces: `group_by_date(papers: list[dict]) -> dict[str, list[dict]]`, `latest_date(papers: list[dict]) -> str | None`, `category_counts(papers: list[dict], date: str) -> dict[str, int]` — used by `agent/research_prompt.md` (Task 6) for the daily agent's own quota self-check; not required by `build_site.py`, which embeds the full dataset and lets client-side JS do its own grouping.

- [ ] **Step 1: Write the failing tests**

`tests/test_site_data.py`:
```python
from scripts.site_data import group_by_date, latest_date, category_counts


def make_paper(id, date, category="neuroscience"):
    return {"id": id, "date_surfaced": date, "category": category}


def test_group_by_date_splits_papers_by_date():
    papers = [make_paper("a", "2026-07-24"), make_paper("b", "2026-07-25"), make_paper("c", "2026-07-25")]
    groups = group_by_date(papers)
    assert set(groups.keys()) == {"2026-07-24", "2026-07-25"}
    assert len(groups["2026-07-25"]) == 2


def test_latest_date_returns_max_date():
    papers = [make_paper("a", "2026-07-24"), make_paper("b", "2026-07-25")]
    assert latest_date(papers) == "2026-07-25"


def test_latest_date_returns_none_for_empty_list():
    assert latest_date([]) is None


def test_category_counts_counts_per_category_for_given_date():
    papers = [
        make_paper("a", "2026-07-25", "neuroscience"),
        make_paper("b", "2026-07-25", "cell_therapy"),
        make_paper("c", "2026-07-25", "cell_therapy"),
        make_paper("d", "2026-07-24", "cell_therapy"),
    ]
    counts = category_counts(papers, "2026-07-25")
    assert counts == {"neuroscience": 1, "cell_therapy": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_site_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.site_data'`

- [ ] **Step 3: Implement scripts/site_data.py**

```python
def group_by_date(papers):
    groups = {}
    for paper in papers:
        date = paper["date_surfaced"]
        groups.setdefault(date, []).append(paper)
    return groups


def latest_date(papers):
    dates = {paper["date_surfaced"] for paper in papers}
    return max(dates) if dates else None


def category_counts(papers, date):
    counts = {}
    for paper in papers:
        if paper["date_surfaced"] == date:
            counts[paper["category"]] = counts.get(paper["category"], 0) + 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_site_data.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/site_data.py tests/test_site_data.py
git commit -m "Add date-grouping helpers for quota self-checks"
git push
```

---

### Task 4: Site template and build script (TDD)

**Files:**
- Create: `site/artifact_template.html`
- Create: `scripts/build_site.py`
- Test: `tests/test_build_site.py`

**Interfaces:**
- Consumes: `validate_papers` from `scripts/validate_papers.py` (Task 2).
- Produces: `render_html(papers: list[dict], template_path: Path) -> str`, `build(data_path=DATA_PATH, template_path=TEMPLATE_PATH, output_path=OUTPUT_PATH) -> Path`, `PLACEHOLDER: str` — used by Task 5 (first publish) and `agent/research_prompt.md` (Task 6).

- [ ] **Step 1: Write the failing tests**

`tests/test_build_site.py`:
```python
import json

from scripts.build_site import render_html, build, PLACEHOLDER

SAMPLE_TEMPLATE = '<html><body><script id="papers-data" type="application/json">__PAPERS_DATA__</script></body></html>'


def make_valid_paper():
    return {
        "id": "test-1", "title": "Test Paper", "link": "https://example.com/paper",
        "summary": "A test summary.", "journal": "Test Journal", "year": 2026,
        "category": "neuroscience", "date_surfaced": "2026-07-25",
        "retraction_status": "No retraction found.", "citation_count": 10,
        "citation_source": "Semantic Scholar", "citation_checked_date": "2026-07-24",
        "contradicting_papers": [],
    }


def test_render_html_embeds_papers_as_valid_json(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    papers = [make_valid_paper()]

    html = render_html(papers, template_path)

    assert PLACEHOLDER not in html
    start = html.index('type="application/json">') + len('type="application/json">')
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end])
    assert embedded == papers


def test_render_html_raises_if_placeholder_missing(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text("<html>no placeholder here</html>", encoding="utf-8")

    try:
        render_html([], template_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert PLACEHOLDER in str(e)


def test_render_html_escapes_script_close_tags_in_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    paper = make_valid_paper()
    paper["summary"] = "Contains a literal </script> tag in the text."

    html = render_html([paper], template_path)

    assert html.count("</script>") == 1
    assert "<\\/script>" in html


def test_build_writes_output_file_for_valid_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    data_path = tmp_path / "papers.json"
    data_path.write_text(json.dumps([make_valid_paper()]), encoding="utf-8")
    output_path = tmp_path / "dist" / "index.html"

    result_path = build(data_path=data_path, template_path=template_path, output_path=output_path)

    assert result_path == output_path
    assert output_path.exists()
    assert PLACEHOLDER not in output_path.read_text(encoding="utf-8")


def test_build_raises_on_invalid_data(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    data_path = tmp_path / "papers.json"
    bad_paper = make_valid_paper()
    del bad_paper["title"]
    data_path.write_text(json.dumps([bad_paper]), encoding="utf-8")
    output_path = tmp_path / "dist" / "index.html"

    try:
        build(data_path=data_path, template_path=template_path, output_path=output_path)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "title" in str(e)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_build_site.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.build_site'`

- [ ] **Step 3: Implement scripts/build_site.py**

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_papers import validate_papers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "papers.json"
TEMPLATE_PATH = ROOT / "site" / "artifact_template.html"
OUTPUT_PATH = ROOT / "site" / "dist" / "index.html"
PLACEHOLDER = "__PAPERS_DATA__"


def load_papers(path=DATA_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_html(papers, template_path=TEMPLATE_PATH):
    template = Path(template_path).read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise ValueError(f"Template is missing the {PLACEHOLDER} placeholder")
    data_json = json.dumps(papers, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, data_json)


def build(data_path=DATA_PATH, template_path=TEMPLATE_PATH, output_path=OUTPUT_PATH):
    papers = load_papers(data_path)
    errors = validate_papers(papers)
    if errors:
        raise ValueError("papers.json failed validation:\n" + "\n".join(errors))
    html = render_html(papers, template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    written_path = build()
    print(f"Wrote {written_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_build_site.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Write site/artifact_template.html**

This is the actual page design (magazine-feed layout, Today/Archive tabs, category filter chips, expand-in-place detail, localStorage-based mark buttons). Design plan: cool pale-sage paper background (not warm cream), near-black ink with a teal-green bias, a deep-teal accent nodding to fluorescence-microscopy green without being neon, a journal-serif display face paired with a system sans for UI chrome and tabular monospace for citation counts/dates. Hairline rules separate cards instead of rounded accent-bar cards; category shown as a small uppercase label, not a colored bar.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Research Digest</title>
<style>
  :root {
    --bg: #f1f3f0;
    --surface: #ffffff;
    --ink: #16211d;
    --ink-muted: #5c6b66;
    --line: #d3d9d5;
    --accent: #0d7a72;
    --accent-ink: #ffffff;
    --warn: #b5762a;
    --critical: #a63d34;
    --font-display: 'Iowan Old Style', 'Palatino Linotype', Palatino, 'URW Palladio L', Georgia, serif;
    --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'SF Mono', 'Cascadia Code', 'Consolas', ui-monospace, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #101613; --surface: #182019; --ink: #e6ece8; --ink-muted: #8fa39c;
      --line: #28332e; --accent: #3fd9c7; --accent-ink: #0a1512; --warn: #d99a4e; --critical: #d9695d;
    }
  }
  :root[data-theme="dark"] {
    --bg: #101613; --surface: #182019; --ink: #e6ece8; --ink-muted: #8fa39c;
    --line: #28332e; --accent: #3fd9c7; --accent-ink: #0a1512; --warn: #d99a4e; --critical: #d9695d;
  }
  :root[data-theme="light"] {
    --bg: #f1f3f0; --surface: #ffffff; --ink: #16211d; --ink-muted: #5c6b66;
    --line: #d3d9d5; --accent: #0d7a72; --accent-ink: #ffffff; --warn: #b5762a; --critical: #a63d34;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-body);
    line-height: 1.5;
  }
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }
  .wrap { max-width: 680px; margin: 0 auto; padding: 32px 20px 96px; }
  header.masthead { border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 20px; }
  header.masthead h1 {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 1.9rem;
    margin: 0 0 4px;
    text-wrap: balance;
  }
  header.masthead .date-line {
    color: var(--ink-muted);
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
  }
  nav.tabs { display: flex; gap: 4px; margin: 20px 0 12px; }
  nav.tabs button {
    font-family: var(--font-body);
    font-size: 0.9rem;
    background: none;
    border: 1px solid var(--line);
    color: var(--ink-muted);
    padding: 6px 14px;
    cursor: pointer;
  }
  nav.tabs button[aria-selected="true"] {
    color: var(--accent-ink);
    background: var(--accent);
    border-color: var(--accent);
  }
  nav.tabs button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 24px; }
  .chip {
    font-family: var(--font-body);
    font-size: 0.72rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    border: 1px solid var(--line);
    color: var(--ink-muted);
    background: none;
    padding: 4px 10px;
    cursor: pointer;
  }
  .chip[aria-pressed="true"] { color: var(--accent-ink); background: var(--accent); border-color: var(--accent); }
  .chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .archive-date {
    font-family: var(--font-body);
    font-size: 0.78rem;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 28px 0 8px;
  }
  .card { border-top: 1px solid var(--line); padding: 18px 0; }
  .card-head { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; }
  .card-head-main { flex: 1; }
  .card h2 {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 1.15rem;
    margin: 0 0 6px;
    text-wrap: balance;
  }
  .card .meta {
    font-size: 0.78rem;
    color: var(--ink-muted);
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 8px;
    font-variant-numeric: tabular-nums;
  }
  .card .meta .tag { text-transform: uppercase; letter-spacing: 0.03em; }
  .card p.summary { margin: 0; max-width: 62ch; }
  .card .actions { display: flex; gap: 8px; margin-top: 10px; }
  .card .actions button {
    font-family: var(--font-body);
    font-size: 0.75rem;
    background: none;
    border: 1px solid var(--line);
    color: var(--ink-muted);
    padding: 4px 10px;
    cursor: pointer;
  }
  .card .actions button.active-used { border-color: var(--accent); color: var(--accent); }
  .card .actions button.active-skip { border-color: var(--critical); color: var(--critical); }
  .card .actions button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .card.marked-skip { opacity: 0.55; }
  .detail { display: none; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--line); font-size: 0.85rem; }
  .card.expanded .detail { display: block; }
  .detail dt { color: var(--ink-muted); text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.04em; margin-top: 10px; }
  .detail dt:first-child { margin-top: 0; }
  .detail dd { margin: 2px 0 0; }
  .detail ol { margin: 4px 0 0; padding-left: 20px; }
  .detail a { color: var(--accent); }
  .empty-state { padding: 48px 0; text-align: center; color: var(--ink-muted); font-family: var(--font-display); font-size: 1.1rem; }
  a.outlink { color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor; }
  a.outlink:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <h1>Research Digest</h1>
    <div class="date-line" id="date-line"></div>
  </header>

  <nav class="tabs" role="tablist">
    <button type="button" id="tab-today" role="tab" aria-selected="true">Today</button>
    <button type="button" id="tab-archive" role="tab" aria-selected="false">Archive</button>
  </nav>

  <div class="chips" id="chips"></div>

  <main id="feed"></main>
</div>

<script id="papers-data" type="application/json">__PAPERS_DATA__</script>
<script>
(function () {
  var ALL_PAPERS = JSON.parse(document.getElementById('papers-data').textContent);

  var CATEGORY_LABELS = {
    cell_therapy: 'Cell Therapy',
    regenerative_medicine: 'Regenerative Medicine',
    clinical_trial: 'Clinical Trial',
    neuroscience: 'Neuroscience',
    ai_biology: 'AI + Biology',
    biomedical_devices: 'Biomedical Devices',
    tissue_engineering: 'Tissue Engineering',
    gene_therapy: 'Gene Therapy'
  };

  var MARKS_KEY = 'research-digest-marks-v1';
  var state = {
    tab: 'today',
    category: null,
    marks: loadMarks()
  };

  function loadMarks() {
    try {
      return JSON.parse(window.localStorage.getItem(MARKS_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveMarks() {
    window.localStorage.setItem(MARKS_KEY, JSON.stringify(state.marks));
  }

  function latestDate(papers) {
    var dates = papers.map(function (p) { return p.date_surfaced; });
    if (dates.length === 0) return null;
    return dates.reduce(function (a, b) { return a > b ? a : b; });
  }

  function groupByDate(papers) {
    var groups = {};
    papers.forEach(function (p) {
      (groups[p.date_surfaced] = groups[p.date_surfaced] || []).push(p);
    });
    return groups;
  }

  function renderChips() {
    var chipsEl = document.getElementById('chips');
    chipsEl.innerHTML = '';
    var allBtn = makeChip('All', state.category === null, function () {
      state.category = null;
      render();
    });
    chipsEl.appendChild(allBtn);
    Object.keys(CATEGORY_LABELS).forEach(function (slug) {
      var btn = makeChip(CATEGORY_LABELS[slug], state.category === slug, function () {
        state.category = state.category === slug ? null : slug;
        render();
      });
      chipsEl.appendChild(btn);
    });
  }

  function makeChip(label, pressed, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.textContent = label;
    btn.setAttribute('aria-pressed', String(pressed));
    btn.addEventListener('click', onClick);
    return btn;
  }

  function markLabel(paperId) {
    return state.marks[paperId];
  }

  function setMark(paperId, value) {
    if (state.marks[paperId] === value) {
      delete state.marks[paperId];
    } else {
      state.marks[paperId] = value;
    }
    saveMarks();
    render();
  }

  function renderCard(paper) {
    var card = document.createElement('article');
    card.className = 'card';
    var mark = markLabel(paper.id);
    if (mark === 'skip') card.classList.add('marked-skip');

    var head = document.createElement('div');
    head.className = 'card-head';
    head.addEventListener('click', function () {
      card.classList.toggle('expanded');
    });

    var main = document.createElement('div');
    main.className = 'card-head-main';

    var h2 = document.createElement('h2');
    h2.textContent = paper.title;
    main.appendChild(h2);

    var meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML =
      '<span class="tag">' + (CATEGORY_LABELS[paper.category] || paper.category) + '</span>' +
      '<span>' + paper.journal + ' &middot; ' + paper.year + '</span>' +
      '<span>' + paper.citation_count.toLocaleString() + ' cites</span>';
    main.appendChild(meta);

    var summary = document.createElement('p');
    summary.className = 'summary';
    summary.textContent = paper.summary;
    main.appendChild(summary);

    var actions = document.createElement('div');
    actions.className = 'actions';
    var usedBtn = document.createElement('button');
    usedBtn.type = 'button';
    usedBtn.textContent = 'Used for video';
    if (mark === 'used') usedBtn.classList.add('active-used');
    usedBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      setMark(paper.id, 'used');
    });
    var skipBtn = document.createElement('button');
    skipBtn.type = 'button';
    skipBtn.textContent = 'Not interested';
    if (mark === 'skip') skipBtn.classList.add('active-skip');
    skipBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      setMark(paper.id, 'skip');
    });
    actions.appendChild(usedBtn);
    actions.appendChild(skipBtn);
    main.appendChild(actions);

    head.appendChild(main);
    card.appendChild(head);

    var detail = document.createElement('dl');
    detail.className = 'detail';

    var linkDt = document.createElement('dt');
    linkDt.textContent = 'Link';
    var linkDd = document.createElement('dd');
    var a = document.createElement('a');
    a.href = paper.link;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'outlink';
    a.textContent = paper.link;
    a.addEventListener('click', function (e) { e.stopPropagation(); });
    linkDd.appendChild(a);

    var retractionDt = document.createElement('dt');
    retractionDt.textContent = 'Retraction / correction status';
    var retractionDd = document.createElement('dd');
    retractionDd.textContent = paper.retraction_status;

    var citationDt = document.createElement('dt');
    citationDt.textContent = 'Citation count';
    var citationDd = document.createElement('dd');
    citationDd.textContent = paper.citation_count.toLocaleString() + ' (' + paper.citation_source + ', checked ' + paper.citation_checked_date + ')';

    detail.appendChild(linkDt);
    detail.appendChild(linkDd);
    detail.appendChild(retractionDt);
    detail.appendChild(retractionDd);
    detail.appendChild(citationDt);
    detail.appendChild(citationDd);

    var contraDt = document.createElement('dt');
    contraDt.textContent = 'Contradicting papers';
    detail.appendChild(contraDt);
    var contraDd = document.createElement('dd');
    if (paper.contradicting_papers.length === 0) {
      contraDd.textContent = 'None found';
    } else {
      var ol = document.createElement('ol');
      paper.contradicting_papers.forEach(function (cp) {
        var li = document.createElement('li');
        var cpA = document.createElement('a');
        cpA.href = cp.link;
        cpA.target = '_blank';
        cpA.rel = 'noopener noreferrer';
        cpA.className = 'outlink';
        cpA.textContent = cp.title;
        cpA.addEventListener('click', function (e) { e.stopPropagation(); });
        li.appendChild(cpA);
        ol.appendChild(li);
      });
      contraDd.appendChild(ol);
    }
    detail.appendChild(contraDd);

    card.appendChild(detail);
    return card;
  }

  function currentPapers() {
    var latest = latestDate(ALL_PAPERS);
    var groups = groupByDate(ALL_PAPERS);
    var papers;
    if (state.tab === 'today') {
      papers = latest ? (groups[latest] || []) : [];
    } else {
      papers = ALL_PAPERS.filter(function (p) { return p.date_surfaced !== latest; });
    }
    if (state.category) {
      papers = papers.filter(function (p) { return p.category === state.category; });
    }
    return { papers: papers, latest: latest };
  }

  function render() {
    document.getElementById('tab-today').setAttribute('aria-selected', String(state.tab === 'today'));
    document.getElementById('tab-archive').setAttribute('aria-selected', String(state.tab === 'archive'));
    renderChips();

    var feed = document.getElementById('feed');
    feed.innerHTML = '';

    if (ALL_PAPERS.length === 0) {
      var empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No digest yet -- check back once the first daily run completes.';
      feed.appendChild(empty);
      document.getElementById('date-line').textContent = '';
      return;
    }

    var result = currentPapers();
    document.getElementById('date-line').textContent = result.latest ? 'Latest digest: ' + result.latest : '';

    if (state.tab === 'today') {
      result.papers.forEach(function (p) { feed.appendChild(renderCard(p)); });
    } else {
      var groups = groupByDate(result.papers);
      Object.keys(groups).sort().reverse().forEach(function (date) {
        var heading = document.createElement('div');
        heading.className = 'archive-date';
        heading.textContent = date;
        feed.appendChild(heading);
        groups[date].forEach(function (p) { feed.appendChild(renderCard(p)); });
      });
    }

    if (result.papers.length === 0) {
      var noResults = document.createElement('div');
      noResults.className = 'empty-state';
      noResults.textContent = 'No papers match this filter.';
      feed.appendChild(noResults);
    }
  }

  document.getElementById('tab-today').addEventListener('click', function () {
    state.tab = 'today';
    render();
  });
  document.getElementById('tab-archive').addEventListener('click', function () {
    state.tab = 'archive';
    render();
  });

  render();
})();
</script>
</body>
</html>
```

- [ ] **Step 6: Commit**

```bash
git add site/artifact_template.html scripts/build_site.py tests/test_build_site.py
git commit -m "Add site template and build script with tests"
git push
```

---

### Task 5: First publish (empty-state Artifact)

**Files:**
- None new — uses `site/dist/index.html` generated by Task 4's build script.

**Interfaces:**
- Consumes: `build()` from `scripts/build_site.py`.
- Produces: a live Artifact URL, to be recorded and reused by every future republish (Task 6/7/8 must always call the Artifact tool with the identical `file_path`).

- [ ] **Step 1: Build the site from the (still-empty) data**

Run: `.venv\Scripts\python -m scripts.build_site`
Expected: `Wrote <repo>\site\dist\index.html`

- [ ] **Step 2: Publish it as a Claude Artifact**

Use the `Artifact` tool with `file_path` pointing at `site/dist/index.html`, `title: "Research Digest"`, `favicon: "🧬"`, and a one-line `description`. This is a direct tool call, not a script — done by whichever Claude session executes this task.

- [ ] **Step 3: Verify the empty state renders correctly**

Open the returned URL (Browser pane) and confirm it shows "No digest yet -- check back once the first daily run completes." with no console errors, and that the Today/Archive tabs and chip row render without crashing on an empty dataset.

- [ ] **Step 4: Record the URL**

Append the published URL to `README.md` under a new `## Live site` heading, commit:
```bash
git add README.md
git commit -m "Record live Artifact URL"
git push
```

---

### Task 6: Daily research-agent prompt

**Files:**
- Create: `agent/research_prompt.md`

**Interfaces:**
- Produces: the exact text that Task 7 passes as the scheduled task's `prompt` argument. Keep this file and the scheduled task in sync — if one changes, update the other via `update_scheduled_task`.

- [ ] **Step 1: Write agent/research_prompt.md**

```markdown
# Daily research digest — agent instructions

You are running as a scheduled daily task. You have no memory of any other
session. Follow these steps exactly, in order.

## 1. Sync the repo

The repo lives at `C:\Users\Lucas\Desktop\claude code\research-aggregator`.

    cd "C:\Users\Lucas\Desktop\claude code\research-aggregator"
    git pull

## 2. Load existing state

Read `data/papers.json`. Note every existing `id` and `title` -- none of
today's picks may duplicate them. Read `data/SCHEMA.md` for the exact field
reference.

## 3. Research today's 10 papers

Categories (must tag every paper with exactly one, from this list):
`cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`,
`ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`.

Rules:
- Exactly 10 new papers today.
- At least 1 each from `cell_therapy`, `regenerative_medicine`,
  `clinical_trial`, `neuroscience`. The remaining 6 may be from any category.
- Search year-descending: try 2026 first, then 2025, 2024, ... down to 2019,
  per category. Prefer the newest strong paper; only drop to an older year if
  that's where the strongest candidate for that slot actually is. Never pick
  a weak paper just to stay recent.
- All four must hold for each paper: (a) groundbreaking/headline research or
  a major review of a hot area, (b) recent per the year rule above,
  (c) well-cited -- get a real citation count from Semantic Scholar or Google
  Scholar and note which source + today's date, (d) has a well-defined
  methods section with good figures (a press release or news article cannot
  be the primary source for a slot, though may be cited as context).
- Never pick a paper whose `id` or `title` already exists in
  `data/papers.json`.
- For each paper, check Retraction Watch, PubPeer, and the journal site for
  retraction/correction history. State explicitly what you found, even if
  "none found" -- never omit this field.
- For each paper, look for 0-5 genuinely contradicting/conflicting papers
  (something that disputes the finding, fails to replicate it, or argues the
  opposite). Never fabricate one to fill a slot -- if none exist, say so.

## 4. Build each paper's JSON entry

Match this exact shape (see `data/SCHEMA.md` for full field docs):

    {
      "id": "<publisher-slug>-<year>-<short-title-slug>",
      "title": "...",
      "link": "https://...",
      "summary": "2-4 sentences, smart layperson audience.",
      "journal": "...",
      "year": 2026,
      "category": "neuroscience",
      "date_surfaced": "<today's ISO date, YYYY-MM-DD>",
      "retraction_status": "...",
      "citation_count": 123,
      "citation_source": "Semantic Scholar",
      "citation_checked_date": "<today's ISO date>",
      "contradicting_papers": [{"title": "...", "link": "..."}]
    }

Append all 10 new entries to the array in `data/papers.json` (do not remove
or edit any existing entries).

## 5. Self-check before committing

Run:

    .venv\Scripts\python -m scripts.validate_papers data\papers.json

If it prints any errors (exit code 1), fix the offending entries in
`data/papers.json` and re-run until it prints `OK: <N> papers valid`.

Also run this quick quota check in Python and confirm the four required
categories each have at least 1 paper with today's `date_surfaced`:

    .venv\Scripts\python -c "
    import json
    from scripts.site_data import category_counts
    papers = json.load(open('data/papers.json', encoding='utf-8'))
    from datetime import date
    today = date.today().isoformat()
    counts = category_counts(papers, today)
    required = {'cell_therapy', 'regenerative_medicine', 'clinical_trial', 'neuroscience'}
    missing = [c for c in required if counts.get(c, 0) == 0]
    total = sum(counts.values())
    print('counts:', counts)
    print('total today:', total)
    print('missing required categories:', missing)
    "

If `total today` is not 10, or `missing required categories` is non-empty,
fix `data/papers.json` and re-run both checks before continuing.

## 6. Commit and push

    git add data/papers.json
    git commit -m "Add daily digest for <today's ISO date>"
    git push

## 7. Rebuild and republish the site

    .venv\Scripts\python -m scripts.build_site

Then call the `Artifact` tool with `file_path` set to
`site/dist/index.html` (the exact same path used for every previous
publish -- check `README.md`'s "Live site" section for the URL this should
match) so the update lands on the existing URL rather than creating a new
one. Reuse `title: "Research Digest"` and `favicon: "🧬"` exactly as before.

## 8. Done

No further action needed. Do not modify `site/artifact_template.html`,
`scripts/*.py`, or anything outside `data/papers.json` during a normal daily
run.
```

- [ ] **Step 2: Commit**

```bash
git add agent/research_prompt.md
git commit -m "Add self-contained daily research-agent prompt"
git push
```

---

### Task 7: Create the scheduled task

**Files:**
- None (tool call only).

**Interfaces:**
- Consumes: the exact text of `agent/research_prompt.md` (Task 6).

- [ ] **Step 1: Read the current prompt file content**

Read `agent/research_prompt.md` in full so the exact current text is used (don't paraphrase it).

- [ ] **Step 2: Create the scheduled task**

Call `create_scheduled_task` with:
- `taskId`: `research-aggregator-daily`
- `description`: `Daily biomedical research digest -- researches, vets, and publishes 10 new papers to the Research Digest Artifact.`
- `cronExpression`: `4 6 * * *` (6:04 AM local -- a few minutes off the hour on purpose, avoiding an exact-round-number pileup)
- `prompt`: the full verbatim text read in Step 1

- [ ] **Step 3: Verify it registered**

Run `list_scheduled_tasks` and confirm `research-aggregator-daily` appears, `enabled: true`, with the expected `nextRunAt`.

---

### Task 8: First manual end-to-end validation

**Files:**
- None (validation only; may touch `data/papers.json` and `site/dist/index.html` as real output of the run).

**Interfaces:**
- Consumes: everything built in Tasks 1-7.

- [ ] **Step 1: Run the prompt once, right now, outside the schedule**

Execute the full instructions in `agent/research_prompt.md` directly in a session today (this is real research work -- expect it to take a while, similar in scope to the original 9-paper sample pass). Do not wait for the cron trigger to test it for the first time.

- [ ] **Step 2: Verify data correctness**

Run: `.venv\Scripts\python -m scripts.validate_papers data\papers.json`
Expected: `OK: 10 papers valid` (or more, if this isn't the very first run).

Run: `git log --oneline -3`
Expected: top commit is the "Add daily digest for ..." commit from Step 1.

- [ ] **Step 3: Verify quota compliance**

Re-run the quota-check snippet from `agent/research_prompt.md` Step 5. Expected: `total today: 10` and `missing required categories: []`.

- [ ] **Step 4: Verify the site rebuilt and republished correctly**

Open the Artifact URL recorded in `README.md` (Browser pane), confirm:
- It is the same URL as Task 5 (no new URL was created).
- The "Today" tab shows exactly today's 10 new cards, each expandable to show retraction status, citation info, and contradicting papers (or "None found").
- Category chips filter correctly.
- Clicking "Used for video" / "Not interested" visually marks a card and survives a page reload (localStorage persistence).
- The "Archive" tab is empty (nothing predates today's first real run) or shows prior days if this isn't the first run.

- [ ] **Step 5: Only after all of the above pass, trust the schedule**

No action needed beyond confirming Task 7's `enabled: true` -- the daily 6:04 AM run will now happen automatically whenever Claude Code Desktop is open around that time (or catch up on next launch, per the confirmed scheduling behavior in the design spec).
