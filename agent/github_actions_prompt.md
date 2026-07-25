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

## 2. Check today's schedule

Lucas controls how many papers get delivered and how often via
`data/schedule.json`, editable from the live site. Run:

    python3 -c "
    import json
    from scripts.schedule import merge_schedule_defaults, is_delivery_day
    from datetime import date

    with open('data/schedule.json', encoding='utf-8') as f:
        raw = json.load(f)
    schedule = merge_schedule_defaults(raw)
    today = date.today()
    print(json.dumps({'is_delivery_day': is_delivery_day(schedule, today), 'schedule': schedule}))
    "

If `is_delivery_day` is `false`, today is not a scheduled delivery day. Do
not research anything, do not touch `data/papers.json`, do not rebuild the
site, do not commit anything. Simply report success with the message "Not a
scheduled delivery day, no digest produced" and stop — this is normal,
expected behavior, not an error or BLOCKED condition.

If `is_delivery_day` is `true`, continue to step 3. Compute today's plan:

    python3 -c "
    import json
    from scripts.schedule import merge_schedule_defaults, compute_plan

    with open('data/schedule.json', encoding='utf-8') as f:
        raw = json.load(f)
    schedule = merge_schedule_defaults(raw)
    print(json.dumps(compute_plan(schedule['count'])))
    "

This prints either `{"mode": "quota", "required_categories": 4, "flexible_slots": N, "overgenerate": M}`
or `{"mode": "open", "target_count": N}`. Keep this plan in mind for steps 4-6.

## 3. Load existing state

Read `data/papers.json`. Note every existing `id` and `title` -- none of
today's picks may duplicate them. Read `data/SCHEMA.md` for the exact field
reference.

## 4. Research candidates for today

Categories (must tag every paper with exactly one, from this list):
`cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`,
`ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`.

**If today's plan has `"mode": "quota"`:**
- Research exactly 1 paper for each of `cell_therapy`, `regenerative_medicine`,
  `clinical_trial`, `neuroscience` (the "required" slots -- these are never
  re-ranked, so pick your single best candidate for each).
- Separately, research `overgenerate` additional qualifying candidate papers
  spanning any of the 8 categories (these are the "flexible" candidates -- step
  6 will automatically narrow these down to `flexible_slots`, so it's fine and
  expected that not all of them will make the final cut). If `overgenerate` is
  0 (i.e. `flexible_slots` is also 0), skip this part entirely -- there are no
  flexible slots today.

**If today's plan has `"mode": "open"`:**
- Research exactly `target_count` qualifying candidate papers spanning any of
  the 8 categories. There is no required-category guarantee in this mode --
  just pick your best `target_count` candidates overall.

Rules (apply to every paper researched, in either mode):
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

## 5. Build each paper's JSON entry

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

In quota mode you now have 4 required-slot entries plus `overgenerate`
flexible-slot candidate entries built in this shape. In open mode you now
have `target_count` entries built in this shape. Do not append anything to
`data/papers.json` yet -- step 6 narrows the flexible candidates first (quota
mode only; open mode skips straight to step 7).

## 6. Narrow the flexible candidates using the trained model

**Skip this entire step in open mode** -- go directly to step 7 with your
`target_count` entries.

**In quota mode:** you should now have 4 required-slot papers plus
`overgenerate` flexible-slot candidates. If `overgenerate` is 0, there's
nothing to narrow -- combine the 4 required-slot papers alone as your final
set and go to step 7. Otherwise, before appending anything to
`data/papers.json`, narrow the flexible candidates down to `flexible_slots`
using the trained re-ranking model:

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

If it prints "cold start, using original order", keep your own first
`flexible_slots` flexible candidates in the order you proposed them and
discard the rest. If it prints "model trained", you'll need to actually run
the ranking: write your flexible candidates to a temporary JSON file, then
run (replacing `<flexible_slots>` with today's actual number)

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
    selected = select_flexible_slots(model, candidates, slot_count=<flexible_slots>)
    print(json.dumps([c['id'] for c in selected]))
    "

and keep only the candidates whose ids are printed, discarding the rest.
Combine those with the 4 required-slot papers for your final set.

## 7. Append to papers.json and self-check

Append your final set of entries (4 + flexible_slots in quota mode, or
target_count in open mode) to the array in `data/papers.json` (do not remove
or edit any existing entries).

The scripts only use the Python standard library, so plain `python3` works
with no setup (`scripts/rank_candidates.py`'s model training needs
scikit-learn, already installed by this workflow's earlier step).

Run:

    python3 -m scripts.validate_papers data/papers.json

If it prints any errors (exit code 1), fix the offending entries in
`data/papers.json` and re-run until it prints `OK: <N> papers valid`.

Also run this quick quota check and confirm today's actual total matches the
plan (4 + flexible_slots in quota mode, or target_count in open mode):

    python3 -c "
    import json
    from scripts.site_data import category_counts
    papers = json.load(open('data/papers.json', encoding='utf-8'))
    from datetime import date
    today = date.today().isoformat()
    counts = category_counts(papers, today)
    total = sum(counts.values())
    print('counts:', counts)
    print('total today:', total)
    "

If `total today` doesn't match today's expected count, fix `data/papers.json`
and re-run both checks before continuing. (In quota mode only, also confirm
each of the 4 required categories has at least 1 paper today -- in open mode
there is no such requirement.)

## 8. Rebuild the site

    python3 -m scripts.build_site

This writes `docs/index.html`, served live by GitHub Pages.

## 9. Update last_delivered_date and commit

Update `data/schedule.json`'s `last_delivered_date` field to today's ISO
date (keep every other field in that file exactly as it was):

    python3 -c "
    import json
    from datetime import date

    with open('data/schedule.json', encoding='utf-8') as f:
        schedule = json.load(f)
    schedule['last_delivered_date'] = date.today().isoformat()
    with open('data/schedule.json', 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2)
        f.write('\n')
    "

Then commit and push everything together:

    git add data/papers.json data/schedule.json docs/index.html
    git commit -m "Add daily digest for <today's ISO date>"
    git push

The workflow's checkout step already configured push credentials scoped to
this repo (via the workflow's `contents: write` permission) -- a plain
`git push` should just work. If it fails, stop and report BLOCKED with the
exact error -- do not attempt workarounds like force-pushing.

## 10. Done

No further action needed. Do not modify `site/artifact_template.html`,
`scripts/*.py`, or anything outside `data/papers.json`, `data/schedule.json`,
and `docs/index.html` during a normal daily run. The live site is
https://lucasrodriggs-tech.github.io/research-aggregator/ -- it updates
automatically within a few minutes of a successful push.
