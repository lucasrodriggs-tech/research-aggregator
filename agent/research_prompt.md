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
  per category. Strongly prefer newer papers: when a newer and an older
  paper both qualify for a slot, the newer one wins by default. Only let an
  older paper win if it's substantially more significant than the newer
  candidate (a genuine landmark, not just "has more citations") -- a
  merely-decent older paper should lose to a good newer one.
- All four must hold for each paper: (a) groundbreaking/headline research or
  a major review of a hot area, (b) recent per the year rule above,
  (c) well-cited -- with one exception: if the paper was published within
  roughly the last 6 months, a low or even single-digit citation count is
  expected and fine -- do not reject or downgrade a recent, groundbreaking
  paper just because it hasn't accumulated citations yet. For papers older
  than ~6 months, a real citation count from Semantic Scholar or Google
  Scholar (note which source + today's date) is expected to actually back
  up the "groundbreaking" claim, (d) has a well-defined methods section with
  good figures (a press release or news article cannot be the primary
  source for a slot, though may be cited as context).
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
