# Global Marks Sync + ML Re-ranking — Design

## Purpose

Two related upgrades to the research digest, requested by Lucas after the core pipeline (daily GitHub Actions job + GitHub Pages site) went live and proved working:

1. **Global marks sync** — "Used for video" / "Not interested" marks currently save to browser `localStorage` only (one device). Lucas wants marking from any device to be visible everywhere, since he's the sole user.
2. **A daily-retraining recommendation model** — a lightweight model that learns from his marks over time and helps pick better papers going forward, retrained as part of the existing daily job.

## Constraints carried over from the existing system

- The site (`docs/index.html`) is fully static, served by GitHub Pages from the public `lucasrodriggs-tech/research-aggregator` repo — no backend, and the page's JS is visible to anyone, so it can never hold a credential capable of writing to the repo.
- The daily job already runs successfully via GitHub Actions (`.github/workflows/daily-digest.yml`), authenticated with a Claude Code OAuth token tied to Lucas's Pro subscription. It clones the repo fresh each run, has full Bash/Python access, and pushes back to `master` using the workflow's own `contents: write` permission.
- 10 papers/day; 4 required-category slots (cell_therapy, regenerative_medicine, clinical_trial, neuroscience) each get exactly 1 pick; the remaining 6 slots are flexible across all 8 tracked categories.

## Label definition (confirmed with Lucas)

Only explicit clicks count as labels. "Used for video" is a positive label; "Not interested" is a negative label. A paper with no mark at all is unlabeled — excluded from training, not treated as either positive or negative. This trades slower data accumulation for a cleaner signal (an unmarked paper might just be one Lucas hasn't gotten to yet, not one he disliked).

## Architecture

### 1. Marks write path — Cloudflare Worker proxy

A small serverless function (Cloudflare Workers free tier) is the only thing with write access to `data/marks.json`. The public page never holds a credential.

- **Endpoint:** `POST /mark` on the Worker, body `{"paper_id": "<id>", "mark": "used" | "not_interested" | null}` (`null` clears an existing mark, matching the current toggle-to-unmark UI behavior).
- **Worker logic:** holds a GitHub Personal Access Token as a Worker secret, scoped narrowly to `lucasrodriggs-tech/research-aggregator` with `contents: write` only (a token Lucas creates specifically for this, separate from anything used elsewhere). On each request: fetch `data/marks.json` via the GitHub Contents API (get current content + SHA), merge in the change (set or delete the key), commit back via the same API using the SHA (standard optimistic-concurrency read-modify-write). On a SHA-mismatch conflict (concurrent write), retry once with a fresh fetch before giving up.
- **Response:** the Worker returns success/failure to the page; the page shows a brief inline "saving…" / "failed, try again" state (optimistic UI update, rolled back on failure).

### 2. Marks read path — direct static fetch, no Worker involved

Since the repo is public, the page reads current mark state by fetching `data/marks.json` directly from `raw.githubusercontent.com/lucasrodriggs-tech/research-aggregator/master/data/marks.json` on load. This replaces the current `localStorage`-based read entirely. No new infrastructure needed for reads — it's a plain static file fetch, same as any other public GitHub content.

### 3. `data/marks.json` shape

```json
{
  "nature-2024-alphafold3": "used",
  "some-other-paper-id": "not_interested"
}
```

Flat object, keyed by the same `id` field already used in `data/papers.json`. Lives in the repo alongside `data/papers.json`, so the daily job can read it with zero extra network calls.

### 4. Training + re-ranking, folded into the existing daily job

Added as new steps in `agent/github_actions_prompt.md` (or a dedicated Python script it invokes), after Claude's research step and before the existing validate/build/commit/push steps:

1. Read `data/marks.json` and `data/papers.json`. Build a training set: for every paper with an explicit mark, `(title + summary + category text, label)` where `used` → 1, `not_interested` → 0.
2. **Cold start:** if there are fewer than 15 labeled examples total, skip training — the pipeline behaves exactly as it does today (no re-ranking).
3. Otherwise, train a lightweight model fresh every run (nothing persisted between runs — retraining from scratch each day is cheap at this scale and avoids model-versioning complexity): `TfidfVectorizer` over the text field, feeding a `LogisticRegression` classifier (both from `scikit-learn`, added as a new dependency for the GitHub Actions job only — not needed locally, since `scripts/*.py` stay stdlib-only).
4. **Where re-ranking applies:** the 4 required-category slots are untouched — Claude still picks the single best qualifying candidate per required category, exactly as today, so the quota guarantee is never put at risk by the model. For the 6 flexible slots, Claude's research step over-generates roughly 12 qualifying candidates (instead of exactly 6) spanning any of the 8 categories. A Python step scores each of those 12 with the trained model and keeps the top 6 by predicted-positive probability. If the model was skipped (cold start), the top 6 are simply Claude's own first 6 in the order it proposed them (unchanged behavior).

## Data flow

```
Lucas's browser (any device)
  → click "Used for video" / "Not interested"
  → POST to Cloudflare Worker
  → Worker updates data/marks.json in the repo via GitHub API
  → page also GETs data/marks.json from raw.githubusercontent.com on load/reload to reflect current state

Daily GitHub Actions job
  → (existing) research 4 required-category picks, exactly as today
  → (new) research ~12 candidates for the 6 flexible slots instead of 6
  → (new) read data/marks.json + data/papers.json, train model if >= 15 labeled examples
  → (new) re-rank the 12 flexible candidates, keep top 6 (or Claude's original top 6 if cold start)
  → (existing, unchanged) assemble 10, validate, build site, commit, push
```

## What this requires from Lucas (cannot be done by the assistant)

- Create a free Cloudflare account and deploy the Worker (code will be provided; deployment via `wrangler` needs Lucas's own interactive login, same shape as today's `gh auth` and `claude setup-token` steps).
- Create a new GitHub Personal Access Token scoped to just this repo's `contents: write`, and store it as a Cloudflare Worker secret.

## Testing

- **Worker:** the merge logic (apply a mark change to the current `marks.json` content) is a pure function, testable in isolation; the GitHub API calls themselves are verified manually against the real repo during setup (mirroring how the GitHub Actions workflow itself was verified end-to-end today), not mocked.
- **Re-ranking/training logic:** implemented as plain Python functions (e.g. `scripts/rank_candidates.py`), unit-tested with pytest using synthetic marks/papers fixtures, consistent with the existing `scripts/` test suite.
- **End-to-end:** before trusting the schedule, do one manual run with a small amount of real seeded mark data to confirm training actually engages past the cold-start threshold, and confirm a mark made in the browser is visible after a page reload.

## Known limitations, accepted for this scope

- Marks and the trained model give no explanation of *why* a paper was ranked where it was — acceptable for a single-user personal tool.
- The 15-label cold-start threshold and the "12 candidates for 6 slots" over-generation factor are reasonable starting points, not empirically tuned — worth revisiting once real usage data exists.
- The Cloudflare Worker is a new piece of infrastructure with its own (separate, narrowly-scoped) credential — a new failure surface, but isolated from the main GitHub Actions pipeline, which remains reliable on its own even if the Worker has issues (marks would just stop syncing, not break the daily digest).
