# Daily research digest — GitHub Actions instructions

You are running as a scheduled GitHub Actions workflow. The repo is already
checked out at the current working directory (no clone/pull needed — every
run starts from a completely fresh checkout of the latest `master`). You
have no memory of any other session. Follow these steps exactly, in order.

## 1. Confirm you're in the right place

Run `pwd` and `ls` and confirm you see a `data/`, `scripts/`, `docs/`,
`agent/` layout. If not, stop and report BLOCKED.

Set a git identity for this commit (GitHub Actions does not set one by
default):

    git config user.name "Research Digest Bot"
    git config user.email "research-digest-bot@users.noreply.github.com"

## 2. Load existing state

Read `data/papers.json`. Note every existing `id` and `title` -- none of
today's picks may duplicate them. Read `data/SCHEMA.md` for the exact field
reference.

## 3. Research candidates for today

Categories (must tag every paper with exactly one, from this list):
`cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`,
`ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`.

Rules:
- Research exactly 1 paper for each of `cell_therapy`, `regenerative_medicine`,
  `clinical_trial`, `neuroscience` (the "required" slots -- these are never
  re-ranked, so pick your single best candidate for each).
- Separately, research 12 additional qualifying candidate papers spanning
  any of the 8 categories (these are the "flexible" candidates -- a later
  step will automatically narrow these 12 down to the final 6, so it's fine
  and expected that not all 12 will make the final cut).
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

You now have 4 required-slot entries and 12 flexible-slot candidate entries
(16 total) built in this shape. Do not append anything to `data/papers.json`
yet -- section 5 narrows the flexible candidates first.

## 5. Narrow the flexible candidates using the trained model

You should now have 4 required-slot papers plus 12 flexible-slot candidates
(16 total). Before appending anything to `data/papers.json`, narrow the 12
flexible candidates down to 6 using the trained re-ranking model:

    python3 -c "
    import json
    from scripts.rank_candidates import train_model, select_flexible_slots

    with open('data/papers.json', encoding='utf-8') as f:
        papers = json.load(f)
    with open('data/marks.json', encoding='utf-8') as f:
        marks = json.load(f)

    model = train_model(papers, marks)
    print('model trained' if model else 'cold start, using original order')
    "

If it prints "cold start, using original order", keep your own first 6
flexible candidates in the order you proposed them and discard the other 6.
If it prints "model trained", you'll need to actually run the ranking:
write your 12 flexible candidates to a temporary JSON file, then run

    python3 -c "
    import json
    from scripts.rank_candidates import train_model, select_flexible_slots

    with open('data/papers.json', encoding='utf-8') as f:
        papers = json.load(f)
    with open('data/marks.json', encoding='utf-8') as f:
        marks = json.load(f)
    with open('/tmp/flexible_candidates.json', encoding='utf-8') as f:
        candidates = json.load(f)

    model = train_model(papers, marks)
    selected = select_flexible_slots(model, candidates, slot_count=6)
    print(json.dumps([c['id'] for c in selected]))
    "

and keep only the 6 candidates whose ids are printed, discarding the other 6.
Combine those 6 with the 4 required-slot papers for a final total of 10.

You now have exactly 10 entries: the 4 required-slot papers plus the 6
selected flexible candidates. Append all 10 to the array in
`data/papers.json` (do not remove or edit any existing entries).

## 6. Self-check before committing

The scripts only use the Python standard library, so plain `python3` works
with no setup.

Run:

    python3 -m scripts.validate_papers data/papers.json

If it prints any errors (exit code 1), fix the offending entries in
`data/papers.json` and re-run until it prints `OK: <N> papers valid`.

Also run this quick quota check and confirm the four required categories
each have at least 1 paper with today's `date_surfaced`:

    python3 -c "
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

## 7. Rebuild the site

    python3 -m scripts.build_site

This writes `docs/index.html`, served live by GitHub Pages.

## 8. Commit and push

    git add data/papers.json docs/index.html
    git commit -m "Add daily digest for <today's ISO date>"
    git push

The workflow's checkout step already configured push credentials scoped to
this repo (via the workflow's `contents: write` permission) -- a plain
`git push` should just work. If it fails, stop and report BLOCKED with the
exact error -- do not attempt workarounds like force-pushing.

## 9. Done

No further action needed. Do not modify `site/artifact_template.html`,
`scripts/*.py`, or anything outside `data/papers.json` and `docs/index.html`
during a normal daily run. The live site is
https://lucasrodriggs-tech.github.io/research-aggregator/ -- it updates
automatically within a few minutes of a successful push.
