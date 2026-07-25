# Digest Frequency & Volume Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Lucas control how many papers (1-10) the daily digest delivers and how often (daily / every other day / twice a week / weekly / every other week / custom calendar), adjustable any time via a control on the live site, taking effect starting the next scheduled run.

**Architecture:** A new `data/schedule.json` file (read/written the same way `data/marks.json` already is) holds the setting. The existing Cloudflare Worker gains a second route to write it from the site. The GitHub Actions cron keeps firing daily unchanged, but the automation's first move each day is now to check `schedule.json` and decide whether today is a delivery day and how many papers to produce.

**Tech Stack:** Python stdlib only (no new dependency), vanilla JS (existing site template), Cloudflare Workers (existing `marks-proxy.js`), pytest (existing).

## Global Constraints

- No access control on the new control (matches the site's existing fully-open security model).
- Setting changes save instantly on change, no separate "Save" button (matches mark-button behavior).
- Setting changes only affect the *next* scheduled check, never retroactively.
- Default state (`{"count": 10, "frequency": "daily", ...}`) reproduces today's exact current behavior — nothing changes for Lucas until he touches the control.
- If count < 4, drop the required-category guarantee entirely; pick the N best qualifying candidates overall instead.
- Custom-mode calendar shows the remaining days of the current month plus all of next month; once every selected custom date is in the past, delivery silently falls back to daily behavior until reconfigured.
- `last_delivered_date` in `schedule.json` is written only by the daily automation job, never by the site/Worker.

---

### Task 1: Data schema + scripts/schedule.py (TDD)

**Files:**
- Create: `data/schedule.json`
- Create: `scripts/schedule.py`
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks (pure stdlib, same style as `scripts/validate_papers.py` and `scripts/rank_candidates.py`).
- Produces: `merge_schedule_defaults(raw: dict | None) -> dict`, `compute_plan(count: int) -> dict`, `is_delivery_day(schedule: dict, today: date) -> bool`, `DEFAULT_SCHEDULE: dict`, `WEEKDAY_ABBREVS: list[str]`, `DEFAULT_DAYS_BY_FREQUENCY: dict`, `VALID_FREQUENCIES: set[str]` — used by Task 3's updated `agent/github_actions_prompt.md`.

- [ ] **Step 1: Create data/schedule.json**

```json
{
  "count": 10,
  "frequency": "daily",
  "days": [],
  "custom_dates": [],
  "last_delivered_date": null
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_schedule.py`:
```python
from datetime import date

from scripts.schedule import (
    merge_schedule_defaults,
    compute_plan,
    is_delivery_day,
    DEFAULT_SCHEDULE,
)


def test_merge_schedule_defaults_fills_missing_file():
    result = merge_schedule_defaults(None)
    assert result == DEFAULT_SCHEDULE


def test_merge_schedule_defaults_overlays_partial_data():
    result = merge_schedule_defaults({"count": 5})
    assert result["count"] == 5
    assert result["frequency"] == "daily"


def test_compute_plan_quota_mode_at_default_ten():
    plan = compute_plan(10)
    assert plan == {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": 6,
        "overgenerate": 12,
    }


def test_compute_plan_quota_mode_no_flexible_slots():
    plan = compute_plan(4)
    assert plan == {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": 0,
        "overgenerate": 0,
    }


def test_compute_plan_quota_mode_small_flexible_uses_minimum_overgenerate():
    plan = compute_plan(5)
    assert plan["flexible_slots"] == 1
    assert plan["overgenerate"] == 4


def test_compute_plan_open_mode_below_four():
    plan = compute_plan(3)
    assert plan == {"mode": "open", "target_count": 3}


def test_is_delivery_day_daily_always_true():
    schedule = merge_schedule_defaults({"frequency": "daily"})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_every_other_day_true_when_no_history():
    schedule = merge_schedule_defaults({"frequency": "every_other_day", "last_delivered_date": None})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_every_other_day_false_next_day():
    schedule = merge_schedule_defaults({
        "frequency": "every_other_day",
        "last_delivered_date": "2026-07-25",
    })
    assert is_delivery_day(schedule, date(2026, 7, 26)) is False


def test_is_delivery_day_every_other_day_true_two_days_later():
    schedule = merge_schedule_defaults({
        "frequency": "every_other_day",
        "last_delivered_date": "2026-07-25",
    })
    assert is_delivery_day(schedule, date(2026, 7, 27)) is True


def test_is_delivery_day_weekly_matches_selected_day():
    # 2026-07-25 is a Saturday
    schedule = merge_schedule_defaults({"frequency": "weekly", "days": ["sat"]})
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True


def test_is_delivery_day_weekly_rejects_other_days():
    # 2026-07-26 is a Sunday
    schedule = merge_schedule_defaults({"frequency": "weekly", "days": ["sat"]})
    assert is_delivery_day(schedule, date(2026, 7, 26)) is False


def test_is_delivery_day_biweekly_requires_both_weekday_and_gap():
    schedule = merge_schedule_defaults({
        "frequency": "biweekly",
        "days": ["sat"],
        "last_delivered_date": "2026-07-25",
    })
    # 2026-08-01 is a Saturday, but only 7 days later -- too soon
    assert is_delivery_day(schedule, date(2026, 8, 1)) is False
    # 2026-08-08 is a Saturday, 14 days later -- eligible
    assert is_delivery_day(schedule, date(2026, 8, 8)) is True


def test_is_delivery_day_custom_matches_listed_date():
    schedule = merge_schedule_defaults({
        "frequency": "custom",
        "custom_dates": ["2026-08-01", "2026-08-15"],
    })
    assert is_delivery_day(schedule, date(2026, 8, 1)) is True
    assert is_delivery_day(schedule, date(2026, 8, 2)) is False


def test_is_delivery_day_custom_falls_back_to_daily_when_exhausted():
    schedule = merge_schedule_defaults({
        "frequency": "custom",
        "custom_dates": ["2026-07-01"],  # entirely in the past relative to the check date below
    })
    assert is_delivery_day(schedule, date(2026, 7, 25)) is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.schedule'`

- [ ] **Step 4: Implement scripts/schedule.py**

```python
import json
from datetime import date

VALID_FREQUENCIES = {
    "daily",
    "every_other_day",
    "twice_weekly",
    "weekly",
    "biweekly",
    "custom",
}

WEEKDAY_ABBREVS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_DAYS_BY_FREQUENCY = {
    "twice_weekly": ["wed", "sat"],
    "weekly": ["sat"],
    "biweekly": ["sat"],
}

DEFAULT_SCHEDULE = {
    "count": 10,
    "frequency": "daily",
    "days": [],
    "custom_dates": [],
    "last_delivered_date": None,
}


def merge_schedule_defaults(raw):
    schedule = dict(DEFAULT_SCHEDULE)
    if raw:
        schedule.update(raw)
    return schedule


def compute_plan(count):
    if count < 4:
        return {"mode": "open", "target_count": count}
    flexible = count - 4
    overgenerate = 0 if flexible == 0 else max(2 * flexible, 4)
    return {
        "mode": "quota",
        "required_categories": 4,
        "flexible_slots": flexible,
        "overgenerate": overgenerate,
    }


def is_delivery_day(schedule, today):
    frequency = schedule["frequency"]
    last = schedule.get("last_delivered_date")
    last_date = date.fromisoformat(last) if last else None

    if frequency == "daily":
        return True

    if frequency == "every_other_day":
        return last_date is None or (today - last_date).days >= 2

    if frequency in ("twice_weekly", "weekly"):
        today_abbrev = WEEKDAY_ABBREVS[today.weekday()]
        return today_abbrev in schedule.get("days", [])

    if frequency == "biweekly":
        today_abbrev = WEEKDAY_ABBREVS[today.weekday()]
        if today_abbrev not in schedule.get("days", []):
            return False
        return last_date is None or (today - last_date).days >= 14

    if frequency == "custom":
        custom_dates = schedule.get("custom_dates", [])
        today_iso = today.isoformat()
        future_or_today = [d for d in custom_dates if d >= today_iso]
        if not future_or_today:
            return True  # exhausted -- fall back to daily behavior
        return today_iso in custom_dates

    raise ValueError(f"unknown frequency: {frequency}")


if __name__ == "__main__":
    with open("data/schedule.json", encoding="utf-8") as f:
        raw = json.load(f)
    schedule = merge_schedule_defaults(raw)
    today = date.today()
    delivery_day = is_delivery_day(schedule, today)
    result = {"is_delivery_day": delivery_day, "schedule": schedule}
    if delivery_day:
        result["plan"] = compute_plan(schedule["count"])
    print(json.dumps(result))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_schedule.py -v`
Expected: all 14 tests PASS

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: all tests (existing 25 + new 14 = 39) PASS

- [ ] **Step 7: Commit**

```bash
git add data/schedule.json scripts/schedule.py tests/test_schedule.py
git commit -m "Add schedule.json schema and delivery-day/plan logic with tests"
git push
```

---

### Task 2: Extend the Worker with a /schedule route

**Files:**
- Modify: `worker/marks-proxy.js`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: a second deployed HTTP endpoint `POST https://<worker-url>/schedule` with body `{"count": int, "frequency": string, "days": string[], "custom_dates": string[]}`, consumed by Task 4's site changes.

No automated tests for this task (per the existing precedent from the marks Worker: verified manually during deployment/end-to-end testing in Task 7, not mocked) — this task is pure content creation, syntax-checked locally with Node.

- [ ] **Step 1: Replace the full contents of worker/marks-proxy.js**

```javascript
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }
    if (request.method !== "POST") {
      return jsonResponse({ error: "method not allowed" }, 405);
    }

    const url = new URL(request.url);
    if (url.pathname === "/mark") {
      return handleMark(request, env);
    }
    if (url.pathname === "/schedule") {
      return handleSchedule(request, env);
    }
    return jsonResponse({ error: "not found" }, 404);
  },
};

async function handleMark(request, env) {
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return jsonResponse({ error: "invalid JSON body" }, 400);
  }

  const paperId = body.paper_id;
  const mark = body.mark;

  if (typeof paperId !== "string" || paperId.length === 0) {
    return jsonResponse({ error: "paper_id is required" }, 400);
  }
  if (mark !== "used" && mark !== "not_interested" && mark !== null) {
    return jsonResponse({ error: "mark must be 'used', 'not_interested', or null" }, 400);
  }

  return writeRepoFile(env, "data/marks.json", `Update mark for ${paperId}`, function (current) {
    if (mark === null) {
      delete current[paperId];
    } else {
      current[paperId] = mark;
    }
    return current;
  });
}

const VALID_FREQUENCIES = ["daily", "every_other_day", "twice_weekly", "weekly", "biweekly", "custom"];
const VALID_DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

async function handleSchedule(request, env) {
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return jsonResponse({ error: "invalid JSON body" }, 400);
  }

  const count = body.count;
  const frequency = body.frequency;
  const days = body.days || [];
  const customDates = body.custom_dates || [];

  if (!Number.isInteger(count) || count < 1 || count > 10) {
    return jsonResponse({ error: "count must be an integer between 1 and 10" }, 400);
  }
  if (!VALID_FREQUENCIES.includes(frequency)) {
    return jsonResponse({ error: `frequency must be one of: ${VALID_FREQUENCIES.join(", ")}` }, 400);
  }
  if (!Array.isArray(days) || !days.every(function (d) { return VALID_DAYS.includes(d); })) {
    return jsonResponse({ error: "days must only contain valid weekday abbreviations" }, 400);
  }
  if (!Array.isArray(customDates) || !customDates.every(function (d) { return DATE_RE.test(d); })) {
    return jsonResponse({ error: "custom_dates must only contain YYYY-MM-DD strings" }, 400);
  }

  return writeRepoFile(env, "data/schedule.json", "Update digest schedule settings", function (current) {
    current.count = count;
    current.frequency = frequency;
    current.days = days;
    current.custom_dates = customDates;
    // last_delivered_date is owned by the daily automation job, never the site.
    return current;
  });
}

async function writeRepoFile(env, path, commitMessage, mutate) {
  const owner = "lucasrodriggs-tech";
  const repo = "research-aggregator";
  const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;

  const maxAttempts = 2;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const getResp = await fetch(apiUrl, { headers: githubHeaders(env) });
    if (!getResp.ok) {
      return jsonResponse({ error: `failed to read ${path}: ${getResp.status}` }, 502);
    }
    const getData = await getResp.json();
    const currentContent = JSON.parse(atob(getData.content));
    const sha = getData.sha;

    const updatedContent = mutate(currentContent);
    const newContentB64 = btoa(JSON.stringify(updatedContent, null, 2) + "\n");

    const putResp = await fetch(apiUrl, {
      method: "PUT",
      headers: githubHeaders(env),
      body: JSON.stringify({
        message: commitMessage,
        content: newContentB64,
        sha: sha,
      }),
    });

    if (putResp.ok) {
      return jsonResponse({ ok: true }, 200);
    }

    if (putResp.status === 409 && attempt < maxAttempts) {
      continue;
    }

    const errText = await putResp.text();
    return jsonResponse({ error: `failed to write ${path}: ${putResp.status} ${errText}` }, 502);
  }

  return jsonResponse({ error: "exhausted retry attempts" }, 500);
}

function githubHeaders(env) {
  return {
    "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "research-aggregator-marks-worker",
    "Content-Type": "application/json",
  };
}

// CORS headers restrict browser-based callers only. This is NOT authentication.
// The Worker URL, once deployed, is publicly POST-able by anyone with the URL
// (e.g., via curl). CORS enforcement happens in browsers, not on this server.
function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "https://lucasrodriggs-tech.github.io",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function jsonResponse(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders() },
  });
}
```

- [ ] **Step 2: Syntax-check with Node**

Run: `node --check worker/marks-proxy.js`
Expected: no output, exit code 0 (a syntax error would print a `SyntaxError` and non-zero exit)

- [ ] **Step 3: Commit**

```bash
git add worker/marks-proxy.js
git commit -m "Add /schedule route to the marks-proxy Worker"
git push
```

---

### Task 3: Update the daily job prompt to be schedule-aware

**Files:**
- Modify: `agent/github_actions_prompt.md` (full-file replacement — nearly every section shifts)

**Interfaces:**
- Consumes: `scripts.schedule.merge_schedule_defaults(raw)`, `scripts.schedule.is_delivery_day(schedule, today)`, `scripts.schedule.compute_plan(count)` (from Task 1).

- [ ] **Step 1: Replace the full contents of agent/github_actions_prompt.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add agent/github_actions_prompt.md
git commit -m "Make the daily prompt schedule-aware (count + delivery-day gating)"
git push
```

---

### Task 4: Settings bar + count/frequency/days controls on the site

**Files:**
- Modify: `site/artifact_template.html`

**Interfaces:**
- Consumes: nothing new from earlier tasks besides the `/schedule` write endpoint from Task 2 (used as a literal URL string, same as `MARK_WRITE_ENDPOINT` already is).
- Produces: `state.schedule`, `DEFAULT_SCHEDULE`, `FREQUENCY_LABELS`, `DEFAULT_DAYS_BY_FREQUENCY`, `shallowCloneSchedule(s)` — consumed by Task 5's calendar addition.

- [ ] **Step 1: Add the settings bar markup**

Find (in the `<body>`, right after the masthead header, before `<nav class="tabs"`):

```html
  <header class="masthead">
    <h1>Research Digest</h1>
    <div class="date-line" id="date-line"></div>
  </header>

  <nav class="tabs" role="tablist">
```

Replace with:

```html
  <header class="masthead">
    <h1>Research Digest</h1>
    <div class="date-line" id="date-line"></div>
  </header>

  <div class="settings-bar">
    <span id="settings-summary"></span>
    <button type="button" id="settings-edit-btn">Edit</button>
  </div>
  <div class="settings-panel" id="settings-panel" hidden></div>

  <nav class="tabs" role="tablist">
```

- [ ] **Step 2: Add CSS for the settings bar and panel**

Find: `#date-chips:empty { display: none; }`
Replace with:

```css
  #date-chips:empty { display: none; }
  .settings-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
    color: var(--ink-muted);
    border: 1px solid var(--line);
    padding: 6px 12px;
    margin: 16px 0;
  }
  .settings-bar button {
    font-family: var(--font-body);
    font-size: 0.78rem;
    background: none;
    border: none;
    color: var(--accent);
    text-decoration: underline;
    cursor: pointer;
    padding: 0;
  }
  .settings-panel { border: 1px solid var(--line); padding: 14px; margin: 0 0 16px; }
  .settings-panel[hidden] { display: none; }
  .settings-panel .field { margin-bottom: 14px; }
  .settings-panel .field:last-child { margin-bottom: 0; }
  .settings-panel label.field-label {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--ink-muted);
    margin-bottom: 6px;
  }
  .settings-panel input[type="range"] { width: 100%; }
  .settings-panel select {
    font-family: var(--font-body);
    font-size: 0.85rem;
    padding: 4px 8px;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--ink);
  }
  .settings-panel .day-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .settings-error { font-size: 0.75rem; color: var(--critical); margin-top: 8px; }
```

- [ ] **Step 3: Add schedule constants and state**

Find:

```javascript
  var MARK_WRITE_ENDPOINT = 'https://research-aggregator-marks.lucas-research-aggregator.workers.dev/mark';
  var MARKS_RAW_URL = 'https://raw.githubusercontent.com/lucasrodriggs-tech/research-aggregator/master/data/marks.json';
  var state = {
    tab: 'today',
    category: null,
    archiveDate: null,
    marks: {},
    markError: null,
    expanded: {}
  };
```

Replace with:

```javascript
  var MARK_WRITE_ENDPOINT = 'https://research-aggregator-marks.lucas-research-aggregator.workers.dev/mark';
  var MARKS_RAW_URL = 'https://raw.githubusercontent.com/lucasrodriggs-tech/research-aggregator/master/data/marks.json';
  var SCHEDULE_WRITE_ENDPOINT = 'https://research-aggregator-marks.lucas-research-aggregator.workers.dev/schedule';
  var SCHEDULE_RAW_URL = 'https://raw.githubusercontent.com/lucasrodriggs-tech/research-aggregator/master/data/schedule.json';

  var FREQUENCY_LABELS = {
    daily: 'Daily',
    every_other_day: 'Every other day',
    twice_weekly: 'Twice a week',
    weekly: 'Once a week',
    biweekly: 'Once every other week',
    custom: 'Custom'
  };

  var DEFAULT_DAYS_BY_FREQUENCY = {
    twice_weekly: ['wed', 'sat'],
    weekly: ['sat'],
    biweekly: ['sat']
  };

  var DAY_LABELS = { sun: 'Sun', mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat' };
  var DAY_ORDER = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

  var DEFAULT_SCHEDULE = {
    count: 10,
    frequency: 'daily',
    days: [],
    custom_dates: [],
    last_delivered_date: null
  };

  var state = {
    tab: 'today',
    category: null,
    archiveDate: null,
    marks: {},
    markError: null,
    expanded: {},
    schedule: DEFAULT_SCHEDULE,
    scheduleEditing: false,
    scheduleError: null
  };
```

- [ ] **Step 4: Add loadSchedule, saveSchedule, and shallowCloneSchedule functions**

Find:

```javascript
  function loadMarks() {
    return fetch(MARKS_RAW_URL, { cache: 'no-store' })
      .then(function (resp) { return resp.ok ? resp.json() : {}; })
      .catch(function () { return {}; });
  }
```

Replace with:

```javascript
  function loadMarks() {
    return fetch(MARKS_RAW_URL, { cache: 'no-store' })
      .then(function (resp) { return resp.ok ? resp.json() : {}; })
      .catch(function () { return {}; });
  }

  function loadSchedule() {
    return fetch(SCHEDULE_RAW_URL, { cache: 'no-store' })
      .then(function (resp) { return resp.ok ? resp.json() : {}; })
      .then(function (raw) {
        var merged = {};
        Object.keys(DEFAULT_SCHEDULE).forEach(function (key) { merged[key] = DEFAULT_SCHEDULE[key]; });
        Object.keys(raw).forEach(function (key) { merged[key] = raw[key]; });
        return merged;
      })
      .catch(function () { return DEFAULT_SCHEDULE; });
  }

  function shallowCloneSchedule(s) {
    return {
      count: s.count,
      frequency: s.frequency,
      days: s.days.slice(),
      custom_dates: s.custom_dates.slice(),
      last_delivered_date: s.last_delivered_date
    };
  }

  function saveSchedule(next) {
    var previous = state.schedule;
    state.schedule = next;
    state.scheduleError = null;
    render();

    fetch(SCHEDULE_WRITE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        count: next.count,
        frequency: next.frequency,
        days: next.days,
        custom_dates: next.custom_dates
      })
    }).then(function (resp) {
      if (!resp.ok) throw new Error('save failed');
    }).catch(function () {
      state.schedule = previous;
      state.scheduleError = true;
      render();
    });
  }
```

- [ ] **Step 5: Add renderSettingsBar and renderSettingsPanel functions**

Find:

```javascript
  function renderDateChips() {
```

Replace with:

```javascript
  function renderSettingsBar() {
    var summary = document.getElementById('settings-summary');
    var s = state.schedule;
    var plural = s.count === 1 ? '' : 's';
    summary.textContent = s.count + ' paper' + plural + '/delivery · ' + FREQUENCY_LABELS[s.frequency];

    var panel = document.getElementById('settings-panel');
    panel.hidden = !state.scheduleEditing;
    document.getElementById('settings-edit-btn').textContent = state.scheduleEditing ? 'Done' : 'Edit';

    if (!state.scheduleEditing) {
      panel.innerHTML = '';
      return;
    }
    renderSettingsPanel(panel);
  }

  function renderSettingsPanel(panel) {
    panel.innerHTML = '';
    var s = state.schedule;

    var countField = document.createElement('div');
    countField.className = 'field';
    var countLabel = document.createElement('label');
    countLabel.className = 'field-label';
    countLabel.textContent = 'Papers per delivery: ' + s.count;
    var countInput = document.createElement('input');
    countInput.type = 'range';
    countInput.min = '1';
    countInput.max = '10';
    countInput.value = String(s.count);
    countInput.addEventListener('input', function () {
      countLabel.textContent = 'Papers per delivery: ' + countInput.value;
    });
    countInput.addEventListener('change', function () {
      var next = shallowCloneSchedule(s);
      next.count = parseInt(countInput.value, 10);
      saveSchedule(next);
    });
    countField.appendChild(countLabel);
    countField.appendChild(countInput);
    panel.appendChild(countField);

    var freqField = document.createElement('div');
    freqField.className = 'field';
    var freqLabel = document.createElement('label');
    freqLabel.className = 'field-label';
    freqLabel.textContent = 'Frequency';
    var freqSelect = document.createElement('select');
    Object.keys(FREQUENCY_LABELS).forEach(function (key) {
      var opt = document.createElement('option');
      opt.value = key;
      opt.textContent = FREQUENCY_LABELS[key];
      if (key === s.frequency) opt.selected = true;
      freqSelect.appendChild(opt);
    });
    freqSelect.addEventListener('change', function () {
      var next = shallowCloneSchedule(s);
      next.frequency = freqSelect.value;
      if (DEFAULT_DAYS_BY_FREQUENCY[freqSelect.value] && next.days.length === 0) {
        next.days = DEFAULT_DAYS_BY_FREQUENCY[freqSelect.value].slice();
      }
      saveSchedule(next);
    });
    freqField.appendChild(freqLabel);
    freqField.appendChild(freqSelect);
    panel.appendChild(freqField);

    if (s.frequency === 'twice_weekly' || s.frequency === 'weekly' || s.frequency === 'biweekly') {
      var daysField = document.createElement('div');
      daysField.className = 'field';
      var daysLabel = document.createElement('label');
      daysLabel.className = 'field-label';
      daysLabel.textContent = 'Days';
      daysField.appendChild(daysLabel);
      var daysRow = document.createElement('div');
      daysRow.className = 'day-chips';
      var singleSelect = s.frequency !== 'twice_weekly';
      DAY_ORDER.forEach(function (day) {
        var pressed = s.days.indexOf(day) !== -1;
        var chip = makeChip(DAY_LABELS[day], pressed, function () {
          var next = shallowCloneSchedule(s);
          if (singleSelect) {
            next.days = pressed ? [] : [day];
          } else {
            if (pressed) {
              next.days = s.days.filter(function (d) { return d !== day; });
            } else {
              next.days = s.days.concat([day]);
            }
          }
          saveSchedule(next);
        });
        daysRow.appendChild(chip);
      });
      daysField.appendChild(daysRow);
      panel.appendChild(daysField);
    }

    if (state.scheduleError) {
      var err = document.createElement('div');
      err.className = 'settings-error';
      err.textContent = "Couldn't save, try again";
      panel.appendChild(err);
    }
  }

  function renderDateChips() {
```

- [ ] **Step 6: Call renderSettingsBar from render() and wire up the Edit/Done button**

Find:

```javascript
    document.getElementById('tab-archive').setAttribute('aria-selected', String(state.tab === 'archive'));
    renderChips();
    renderDateChips();
```

Replace with:

```javascript
    document.getElementById('tab-archive').setAttribute('aria-selected', String(state.tab === 'archive'));
    renderSettingsBar();
    renderChips();
    renderDateChips();
```

Find:

```javascript
  document.getElementById('tab-archive').addEventListener('click', function () {
    state.tab = 'archive';
    render();
  });

  loadMarks().then(function (marks) {
    state.marks = marks;
    render();
  });
})();
```

Replace with:

```javascript
  document.getElementById('tab-archive').addEventListener('click', function () {
    state.tab = 'archive';
    render();
  });
  document.getElementById('settings-edit-btn').addEventListener('click', function () {
    state.scheduleEditing = !state.scheduleEditing;
    render();
  });

  loadMarks().then(function (marks) {
    state.marks = marks;
    render();
  });
  loadSchedule().then(function (schedule) {
    state.schedule = schedule;
    render();
  });
})();
```

- [ ] **Step 7: Rebuild the site locally and manually verify in a browser**

```bash
.venv\Scripts\python -m scripts.build_site
```

Open `docs/index.html` in a browser (or use the Browser pane). Confirm: no
console errors, the settings bar reads "10 papers/delivery · Daily" (the
default, since `data/schedule.json` on this branch/worktree matches the
default), clicking "Edit" expands the panel showing the slider and dropdown,
moving the slider updates the visible label live, and changing the dropdown
to "Twice a week" reveals Wed/Sat day chips (pre-selected, since those are
the defaults). Since the Worker isn't deployed with this new code yet, actual
saves will fail — confirm the "Couldn't save, try again" text appears and
the setting visually reverts, matching the same optimistic-update-and-rollback
pattern already proven for marks.

- [ ] **Step 8: Commit**

```bash
git add site/artifact_template.html docs/index.html
git commit -m "Add settings bar with count/frequency/day controls"
git push
```

---

### Task 5: Custom-mode calendar

**Files:**
- Modify: `site/artifact_template.html`

**Interfaces:**
- Consumes: `state.schedule`, `shallowCloneSchedule`, `saveSchedule`, `.field`/`.field-label` CSS classes (from Task 4).
- Produces: nothing consumed by later tasks — this is the last site-code task.

- [ ] **Step 1: Add calendar CSS**

Find: `.settings-error { font-size: 0.75rem; color: var(--critical); margin-top: 8px; }`
Replace with:

```css
  .settings-error { font-size: 0.75rem; color: var(--critical); margin-top: 8px; }
  .calendar-month { margin-top: 10px; }
  .calendar-heading { font-size: 0.8rem; font-weight: 600; text-align: center; margin-bottom: 6px; }
  .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; text-align: center; font-size: 0.75rem; }
  .calendar-dow { color: var(--ink-muted); text-transform: uppercase; font-size: 0.65rem; padding: 2px 0; }
  .calendar-cell { padding: 5px 0; border: 1px solid var(--line); cursor: pointer; }
  .calendar-cell.empty { border: none; cursor: default; }
  .calendar-cell.disabled { opacity: 0.3; cursor: not-allowed; }
  .calendar-cell.selected {
    border: 2px solid var(--accent);
    background: color-mix(in srgb, var(--accent) 15%, transparent);
    font-weight: 700;
  }
  .clear-dates-link {
    font-family: var(--font-body);
    font-size: 0.75rem;
    background: none;
    border: none;
    color: var(--accent);
    text-decoration: underline;
    cursor: pointer;
    padding: 0;
    margin-top: 8px;
  }
```

- [ ] **Step 2: Add calendar date-math and rendering helper functions**

Find:

```javascript
  function makeChip(label, pressed, onClick) {
```

Replace with:

```javascript
  function daysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
  }

  function pad2(n) { return n < 10 ? '0' + n : String(n); }

  function isoDate(year, month, day) {
    return year + '-' + pad2(month + 1) + '-' + pad2(day);
  }

  function buildMonthCells(year, month) {
    var firstWeekday = new Date(year, month, 1).getDay();
    var total = daysInMonth(year, month);
    var cells = [];
    for (var i = 0; i < firstWeekday; i++) cells.push(null);
    for (var d = 1; d <= total; d++) cells.push(d);
    return cells;
  }

  function renderMonthCalendar(year, month, todayIso, selectedDates, onToggle) {
    var monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    var wrap = document.createElement('div');
    wrap.className = 'calendar-month';
    var heading = document.createElement('div');
    heading.className = 'calendar-heading';
    heading.textContent = monthNames[month] + ' ' + year;
    wrap.appendChild(heading);

    var grid = document.createElement('div');
    grid.className = 'calendar-grid';
    ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].forEach(function (label) {
      var head = document.createElement('div');
      head.className = 'calendar-dow';
      head.textContent = label;
      grid.appendChild(head);
    });

    buildMonthCells(year, month).forEach(function (day) {
      var cell = document.createElement('div');
      cell.className = 'calendar-cell';
      if (day === null) {
        cell.classList.add('empty');
      } else {
        var iso = isoDate(year, month, day);
        cell.textContent = String(day);
        if (iso < todayIso) {
          cell.classList.add('disabled');
        } else {
          if (selectedDates.indexOf(iso) !== -1) cell.classList.add('selected');
          cell.addEventListener('click', function () { onToggle(iso); });
        }
      }
      grid.appendChild(cell);
    });

    wrap.appendChild(grid);
    return wrap;
  }

  function makeChip(label, pressed, onClick) {
```

- [ ] **Step 3: Render the calendar inside renderSettingsPanel when frequency is custom**

Find:

```javascript
    if (state.scheduleError) {
      var err = document.createElement('div');
      err.className = 'settings-error';
      err.textContent = "Couldn't save, try again";
      panel.appendChild(err);
    }
  }
```

Replace with:

```javascript
    if (s.frequency === 'custom') {
      var calField = document.createElement('div');
      calField.className = 'field';
      var calLabel = document.createElement('label');
      calLabel.className = 'field-label';
      calLabel.textContent = 'Delivery days';
      calField.appendChild(calLabel);

      var today = new Date();
      var todayIso = isoDate(today.getFullYear(), today.getMonth(), today.getDate());
      var nextMonthDate = new Date(today.getFullYear(), today.getMonth() + 1, 1);

      function toggleCustomDate(iso) {
        var next = shallowCloneSchedule(s);
        var idx = next.custom_dates.indexOf(iso);
        if (idx === -1) {
          next.custom_dates = next.custom_dates.concat([iso]).sort();
        } else {
          next.custom_dates = next.custom_dates.filter(function (d) { return d !== iso; });
        }
        saveSchedule(next);
      }

      calField.appendChild(renderMonthCalendar(today.getFullYear(), today.getMonth(), todayIso, s.custom_dates, toggleCustomDate));
      calField.appendChild(renderMonthCalendar(nextMonthDate.getFullYear(), nextMonthDate.getMonth(), todayIso, s.custom_dates, toggleCustomDate));

      var clearLink = document.createElement('button');
      clearLink.type = 'button';
      clearLink.className = 'clear-dates-link';
      clearLink.textContent = 'Clear all';
      clearLink.addEventListener('click', function () {
        var next = shallowCloneSchedule(s);
        next.custom_dates = [];
        saveSchedule(next);
      });
      calField.appendChild(clearLink);

      panel.appendChild(calField);
    }

    if (state.scheduleError) {
      var err = document.createElement('div');
      err.className = 'settings-error';
      err.textContent = "Couldn't save, try again";
      panel.appendChild(err);
    }
  }
```

- [ ] **Step 4: Rebuild the site locally and manually verify in a browser**

```bash
.venv\Scripts\python -m scripts.build_site
```

Open `docs/index.html`. Click Edit, switch Frequency to "Custom". Confirm
two month-grid calendars render (current month with only remaining days
clickable, past days visibly greyed out and inert; next month fully
clickable), clicking a day toggles a bordered/highlighted selection state,
"Clear all" empties the selection, and (since the Worker isn't deployed yet)
saves still show the same error-and-revert behavior as Task 4.

- [ ] **Step 5: Commit**

```bash
git add site/artifact_template.html docs/index.html
git commit -m "Add custom-mode calendar for picking specific delivery days"
git push
```

---

### Task 6: Deploy the updated Worker (Lucas only — cannot be automated)

**Files:** none (deployment only).

- [ ] **Step 1: Lucas runs, from the `worker/` directory of this branch/worktree:**

```
wrangler.cmd deploy
```

- [ ] **Step 2: Lucas confirms the deploy succeeded** (prints "Deployed research-aggregator-marks..." with the same live URL as before — the Worker name/URL don't change, only its code).

---

### Task 7: End-to-end validation

**Files:** none (validation only — uses artifacts from all prior tasks).

- [ ] **Step 1: Verify a schedule write round-trips through the real Worker**

After Task 6's deploy, from a browser console or the Browser pane, POST a
test payload directly to the deployed endpoint:

```javascript
fetch('https://research-aggregator-marks.lucas-research-aggregator.workers.dev/schedule', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ count: 7, frequency: 'twice_weekly', days: ['wed', 'sat'], custom_dates: [] })
}).then(r => r.text().then(t => 'status=' + r.status + ' body=' + t))
```

Expected: `status=200 body={"ok":true}`. Then `git pull` in the repo and
`cat data/schedule.json` — confirm it now shows `count: 7`,
`frequency: "twice_weekly"`, `days: ["wed","sat"]`.

- [ ] **Step 2: Reset back to today's actual real settings**

If Step 1's test value shouldn't be the real live setting, POST the actual
desired values (or the default `{"count": 10, "frequency": "daily", "days": [], "custom_dates": []}`)
to the same endpoint to restore the real setting Lucas wants live.

- [ ] **Step 3: Verify the settings bar and panel on the real deployed site**

Navigate to `https://lucasrodriggs-tech.github.io/research-aggregator/`
(cache-bust with a `?v=` query param if GitHub Pages hasn't redeployed yet —
wait for the push from Task 5 to propagate first). Confirm the settings bar
shows the current real setting, clicking Edit expands the panel, and every
control (slider, dropdown, day chips, and — after switching to Custom — the
calendar) reflects and updates state correctly against the live Worker (no
more "Couldn't save" errors, since the Worker is now deployed with the new
route).

- [ ] **Step 4: Verify scripts/schedule.py logic against the real schedule.json**

```bash
.venv\Scripts\python -m scripts.schedule
```

(Note: this requires adding this file to be runnable as `python -m
scripts.schedule` — it already has the `if __name__ == "__main__":` block
from Task 1, so this just confirms it runs cleanly against the real,
currently-live `data/schedule.json` and prints a sensible
`{"is_delivery_day": ..., "schedule": {...}, "plan": {...}}` result.)

- [ ] **Step 5: Trigger the daily workflow manually and confirm it completes**

```bash
gh workflow run daily-digest.yml
```

Poll `gh run view <id> --json status,conclusion` until it's no longer
`in_progress`. Confirm the run succeeds and behaves correctly for whatever
the real live schedule setting is at the time (either producing a fresh
digest sized per `count`, or cleanly reporting "not a scheduled delivery
day" and making no changes — both are valid successful outcomes, distinguish
by checking the run's logs and whether a new commit landed).
