# Daily research digest — cloud routine instructions

You are running as a scheduled Claude Routine in a cloud sandbox environment
(not Lucas's laptop). You have no memory of any other session. Follow these
steps exactly, in order.

## 1. Get the repo

Check whether the repo is already present and up to date; otherwise clone it
fresh. Run this from your working directory:

    if [ -d "research-aggregator/.git" ]; then
      cd research-aggregator && git pull
    elif [ -f ".git/config" ] && git remote -v | grep -q "research-aggregator"; then
      git pull
    else
      git clone https://github.com/lucasrodriggs-tech/research-aggregator.git
      cd research-aggregator
    fi

Confirm you end up with your working directory at the repo root (a `data/`,
`scripts/`, `docs/`, `agent/` layout) before continuing. If `git pull` or
`git clone` fails, stop and report BLOCKED with the exact error -- do not
proceed on stale or missing code.

Set a git identity for commits in this environment (needed before any
commit will succeed here):

    git config user.name "Research Digest Bot"
    git config user.email "research-digest-bot@users.noreply.github.com"

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

This environment does not have a pre-built Python virtualenv -- the scripts
only use the Python standard library, so plain `python3` works with no setup.

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

## 6. Rebuild the site

    python3 -m scripts.build_site

This writes `docs/index.html`. Unlike the site's earlier version, this
environment has no Artifact-publishing tool -- the site is hosted on GitHub
Pages instead, which serves directly from `docs/index.html` in this repo.
There is no separate "publish" step: committing and pushing the file (next
step) is what makes it live.

## 7. Commit and push

    git add data/papers.json docs/index.html
    git commit -m "Add daily digest for <today's ISO date>"
    git push

If the push fails due to authentication, stop and report BLOCKED with the
exact error -- do not attempt workarounds like force-pushing or changing
remotes.

## 8. Done

No further action needed. Do not modify `site/artifact_template.html`,
`scripts/*.py`, or anything outside `data/papers.json` and `docs/index.html`
during a normal daily run. The live site is
https://lucasrodriggs-tech.github.io/research-aggregator/ -- it updates
automatically within a few minutes of a successful push, no manual publish
step required.
