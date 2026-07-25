# Digest Frequency & Volume Control — Design Spec

**Status:** Approved 2026-07-25, ready for implementation planning.

## Problem

The daily digest currently always delivers a fixed 10 papers, every day, with no
way to adjust. Lucas finds going through 10 new papers a day, every day, more
than he can realistically handle. He wants to control both **how many** papers
get delivered per event, and **how often** delivery events happen — and to be
able to change either at any time, taking effect starting the next scheduled
run.

## Requirements (from Lucas, confirmed during brainstorming)

- Count: 1–10 papers per delivery, adjustable at any time.
- Frequency, one of:
  - **Daily** (today's current behavior)
  - **Every other day**
  - **Twice a week** — selectable day pair, defaults to Wed + Sat
  - **Once a week** — selectable day, defaults to Sat
  - **Once every other week** — selectable day, defaults to Sat
  - **Custom** — an explicit set of calendar dates
- Changing a setting takes effect starting the *next* scheduled check (the next
  6am-ish GitHub Actions run) — never retroactive.
- No access control on the new control — matches the site's existing fully-open
  security model (mark buttons already have none; this is a single-user site).
- If the chosen count is below 4 (the number of "required" categories:
  `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`),
  drop the per-category guarantee entirely and just pick the N best qualifying
  candidates overall, regardless of category.
- Custom calendar: shows the remaining days of the current month plus the
  full next month, so ~5–6 weeks are selectable in one view. Once all selected
  custom dates are in the past, delivery silently falls back to daily behavior
  (10, or whatever count is set) until Lucas reconfigures — it never goes
  silent/stuck with no digests.
- All setting changes save instantly on change (no separate "Save" button),
  matching how the mark buttons already behave.

## Data Model

New file, `data/schedule.json`, committed to the repo (same pattern as
`data/marks.json`):

```json
{
  "count": 10,
  "frequency": "daily",
  "days": [],
  "custom_dates": [],
  "last_delivered_date": "2026-07-25"
}
```

- `count`: integer 1–10.
- `frequency`: one of `"daily"`, `"every_other_day"`, `"twice_weekly"`,
  `"weekly"`, `"biweekly"`, `"custom"`.
- `days`: array of lowercase weekday abbreviations (`"sun"`..`"sat"`), only
  meaningful for `twice_weekly` / `weekly` / `biweekly`. Ignored otherwise.
- `custom_dates`: array of ISO date strings (`"YYYY-MM-DD"`), only meaningful
  for `frequency: "custom"`. Ignored otherwise.
- `last_delivered_date`: ISO date string, the date of the most recent
  *successful* delivery. Written only by the daily automation job (never by
  the site or the Worker), since it reflects actual delivery history rather
  than a settings change.

If `data/schedule.json` does not exist, all consumers (site and daily job)
treat it as `{"count": 10, "frequency": "daily", "days": [], "custom_dates": [],
"last_delivered_date": null}` — i.e., today's current behavior, so nothing
changes for Lucas until he actually touches the control.

**Default days per frequency** (used when a user switches *to* a weekly-type
frequency and `days` is still empty): `twice_weekly` → `["wed", "sat"]`,
`weekly` → `["sat"]`, `biweekly` → `["sat"]`.

## Site UI

A thin summary bar sits directly under the masthead header, always visible on
both the Today and Archive tabs, showing the current setting in plain text,
e.g. `10 papers/day · Daily`, with an **Edit** link.

Clicking Edit expands the bar in place (no modal, no page navigation) to show:

- **Count**: a range slider, 1–10, with the current value shown as a number
  next to it.
- **Frequency**: a `<select>` dropdown with the six options listed above.
- **Days** (only rendered when frequency is `twice_weekly` / `weekly` /
  `biweekly`): a row of day-abbreviation toggle chips (Sun–Sat), reusing the
  existing `.chip` visual style from the category filter chips. Multiple chips
  can be active only for `twice_weekly` (exactly 2 expected, though the UI
  doesn't hard-block a different count); `weekly`/`biweekly` behave as a
  single-select (selecting a new day chip deselects the previous one).
- **Calendar** (only rendered when frequency is `custom`): a month-grid
  calendar covering the remaining days of the current month plus all of next
  month. Selected days get a bordered/highlighted square (accent-color border
  + light accent-tint background), not a filled circle. Days already in the
  past are greyed out and unclickable. A "Clear all" link resets the
  selection. No month-navigation arrows beyond the fixed ~5–6 week window
  described above.

Every control writes its change immediately (optimistic update + rollback on
failure, following the exact same pattern `setMark` already uses for marks) by
POSTing the *entire* current settings object to the Worker — not a partial
patch — so the Worker's read-modify-write logic mirrors what it already does
for `marks.json`.

## Worker Changes

The existing `worker/marks-proxy.js` gains a second route:

```
POST /schedule
Body: {"count": 7, "frequency": "twice_weekly", "days": ["wed","sat"], "custom_dates": []}
```

- Validates: `count` is an integer 1–10; `frequency` is one of the six valid
  strings; `days` (if present) only contains valid weekday abbreviations;
  `custom_dates` (if present) only contains valid `YYYY-MM-DD` strings.
- On success: reads current `data/schedule.json` via the GitHub Contents API,
  merges in the new `count`/`frequency`/`days`/`custom_dates` (preserving the
  existing `last_delivered_date` untouched — the site never sends or
  overwrites that field), writes back with the same sha-conflict-retry logic
  already used for marks.
- Reuses the same `GITHUB_TOKEN` secret and CORS setup already configured —
  no new Cloudflare secret or deploy-time config needed.

## Daily Automation Logic Changes

`.github/workflows/daily-digest.yml`'s cron trigger is unchanged — it still
fires once daily. The first steps of `agent/github_actions_prompt.md` change:

1. Read `data/schedule.json` (or the default above if it doesn't exist).
2. Compute **is today a delivery day?**
   - `daily` → always yes.
   - `every_other_day` → yes if `last_delivered_date` is null, or today minus
     `last_delivered_date` is ≥ 2 days.
   - `twice_weekly` / `weekly` → yes if today's weekday is in `days`.
   - `biweekly` → yes if today's weekday is in `days` **and** (`last_delivered_date`
     is null or today minus `last_delivered_date` is ≥ 14 days) — the extra
     gate is what makes it fire every *other* matching weekday rather than
     every one.
   - `custom` → yes if today's ISO date is in `custom_dates`. If `custom_dates`
     contains no dates that are today-or-future, treat this the same as
     `daily` (the silent fallback described above).
3. **Not a delivery day:** exit immediately. No research, no new
   `data/papers.json` entries, no site rebuild, no commit.
4. **Is a delivery day:** proceed largely as today, except the target count is
   `schedule.count` instead of a hardcoded 10:
   - If `count >= 4`: keep the current required-category guarantee (1 each of
     the 4 required categories, remaining `count - 4` as flexible slots).
     Flexible-slot over-generation scales with the target instead of always
     being a fixed 12: research `2 * (count - 4)` flexible candidates (minimum
     4, to preserve real selection breadth even when only 1-2 flexible slots
     are needed), then narrow down to `count - 4` via the ML re-ranking model
     exactly as today. At the current default (`count=10`), this reproduces
     today's exact 12-candidates-narrowed-to-6 behavior.
   - If `count < 4`: skip the required-category logic entirely; research
     `count` qualifying candidates from any category and take the model's
     top-ranked `count` of them (or just the researcher's own top picks if the
     model hasn't trained yet), same quality bar (groundbreaking, recent,
     cited, retraction-checked) as always.
5. After a successful commit, also update `last_delivered_date` to today's
   date inside the same `data/papers.json`-touching commit (schedule.json's
   `last_delivered_date` field gets its own small commit alongside, or is
   folded into the same commit — implementation detail for the plan).

## Edge Cases & Non-Goals

- Setting changes are never retroactive — only affect the next scheduled
  check, per Lucas's explicit request.
- The Worker validates all fields server-side; a malformed request is
  rejected with 400, mirroring the marks endpoint's error handling.
- The marks-sync and ML re-ranking system built previously is untouched:
  re-ranking still only ever affects the flexible slots within whatever count
  is currently configured (and is skipped entirely when count < 4).
- Out of scope: any access control/auth on the new control (explicitly
  declined); a "pause entirely" option (not requested — 1 is the floor);
  multi-month custom scheduling beyond the ~5-6 week window shown.
