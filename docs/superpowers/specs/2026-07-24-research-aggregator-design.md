# Research Paper Aggregator — Design

## Purpose

Lucas is an aspiring science content creator (background: co-authored opioid-neuroscience circuit work at TAMU; currently a researcher in George Eisenhoffer's zebrafish lab at MD Anderson doing quantitative confocal imaging/Imaris analysis on epithelial biology and ROS-driven tissue breakdown). He wants a low-effort way to surface a small, high-quality, daily-refreshed set of research papers to pull video topics from, without having to manually trawl journals himself.

## Subject areas tracked

Neuroscience; AI applied to neuroscience/biology/biomedical research; biomedical devices; regenerative medicine — cell therapy (allogeneic, autologous, xenogeneic); tissue engineering; biomaterials (especially hydrogels); gene therapy; groundbreaking clinical trials/novel treatments.

## Selection criteria (all four should hold for a paper to qualify)

1. Groundbreaking/headline research — original research, or a major review of a genuinely hot area.
2. Relatively recent — search year-descending starting at 2026, falling back to 2025, 2024, ... down to 2019 as needed per category. Prefer the newest possible pick, but don't force a weak/non-groundbreaking paper just to stay recent — drop to an older year if that's where the strongest paper is.
3. Well-cited — report an actual citation count, its source (e.g. Semantic Scholar, Google Scholar), and the date checked, since counts drift.
4. Well-defined methods section with good figures — this generally rules out using a press release or news article as the primary item for a slot, though such pieces may be referenced as context within a paper's write-up.

## Daily volume and category mix

- 10 new papers per day.
- At least 1 must come from each of: cell therapy, regenerative medicine (non-cell-therapy), clinical trial, neuroscience.
- The remaining 6 may come from any tracked subject area (including repeats of the required four).
- No paper already present in `data/papers.json` may be re-selected (dedupe against full history, not just recent days).

## Required fields per paper

- Title
- Link (direct URL, prefer the journal/publisher page or PubMed/PMC over paywalled aggregators when a free version exists)
- 2-4 sentence summary, written for a smart layperson audience (this feeds directly into video research, so it should stay technically honest rather than oversimplified)
- Journal/venue
- Year published
- Retraction/correction history — explicit statement of what was checked (Retraction Watch, PubPeer, journal site) and what was found, even if "none found." Never omit this field.
- Citation count, with source and the date it was checked
- 1-5 contradicting/conflicting papers, if any genuinely exist (a paper that disputes the finding, fails to replicate it, or argues the opposite conclusion), each with title + link. If none exist, say so explicitly — never fabricate one to fill the slot.

## Architecture

Three pieces, tied together by one GitHub repo (Lucas has an existing GitHub account):

1. **Data store — GitHub repo.** Holds `data/papers.json` (append-only history of every paper ever surfaced, one entry per paper with all required fields above, plus its category tag and the date it was surfaced) and `data/marks.json` (Lucas's used/not-interested flags, keyed by paper ID).
2. **Daily scheduled Claude agent.** Uses the `scheduled-tasks` mechanism (`create_scheduled_task`, cron in local time), which is **tied to the Claude Code Desktop app on Lucas's machine, not an independent cloud service** — it fires while the app is open at/after the scheduled time, or catches up on next launch if the app was closed. This was a corrected assumption from the original design (which assumed a fully independent cloud scheduler); Lucas confirmed accepting this behavior for v1 rather than rearchitecting onto GitHub Pages + GitHub Actions for true laptop-independence. Runs once a day (default: 6:00 AM local time — trivially reconfigurable at setup, exact hour not load-bearing to the design). On each run it:
   - Pulls the repo.
   - Performs the research pass per the criteria, quota, and year-descending rules above, deduping against `data/papers.json`.
   - Appends the day's 10 new entries to `data/papers.json` and commits.
   - Regenerates the static site HTML from the full dataset.
   - Republishes the Claude Artifact to the same URL (`Artifact` tool, same file path → same URL, so the link Lucas bookmarks never changes).
3. **Claude Artifact website.** The page Lucas actually visits.
   - **Layout:** magazine feed — single column, full-width cards, summary always visible, generous whitespace. This was chosen over a compact grid and a dense filterable list after a visual mockup comparison (see `.superpowers/brainstorm/` history in this repo for the compared options).
   - **Today view** (default): today's 10 cards. Click a card to expand full detail in place (retraction status, citation count + source/date, contradicting papers) — an accordion, not a separate page.
   - **Archive tab:** browse/search past days' picks.
   - **Category filter chips** above the feed (Neuro / Cell Therapy / Regen Med / Clinical Trial / etc.), since papers are already tagged by category for the quota system, so filtering is cheap to add. (Default choice — Lucas didn't get to confirm/reject this explicitly; easy to remove later if it clutters the "calm magazine" feel.)
   - **Mark buttons** (used / not interested) per card. **v1: browser localStorage** — instant, zero setup, but scoped to one browser/device and invisible to the scheduled agent. **Planned fast-follow:** once a GitHub connector is confirmed callable from a Claude session (see Known dependencies), swap the write target to `data/marks.json` in the GitHub repo via the Artifact `mcp` capability, so marks sync across devices and could eventually inform the agent's own logic.

## Data flow

```
Scheduled agent (daily)
  → WebSearch/WebFetch research pass
  → validate against 4 criteria + quota/dedupe rules
  → append to data/papers.json, commit to GitHub
  → regenerate site HTML from full dataset
  → Artifact tool republishes to the same URL

Lucas's browser (any time, independent of the agent)
  → click "mark" on a card
  → v1: written to localStorage in that browser
  → (fast-follow: GitHub connector via mcp capability writes to data/marks.json instead)
```

## Known dependencies / open items before implementation can complete

- **Scheduling is app-open-dependent, not truly serverless (confirmed 2026-07-24).** The daily job only runs while Claude Code Desktop is open on Lucas's machine around the scheduled time, or on next app launch if it was closed. Accepted for v1. If this later proves too unreliable in practice, the documented escalation path is: move hosting to GitHub Pages and the daily job to a GitHub Actions cron workflow calling the Anthropic API directly (needs Lucas's own API key, small ongoing cost) — a bigger rework, not planned for v1.
- **Scheduled-agent write access to GitHub.** This is a *different* mechanism than the browser-side connector below — a scheduled cloud agent has normal shell/git tool access, so the plan is to authenticate it with a GitHub Personal Access Token (Lucas will need to generate one and make it available to the scheduled task) and commit via plain `git`/`gh` CLI. Not blocked by the connector issue below; to be confirmed when the scheduled task is actually built and run once manually.
- **Browser-side GitHub connector for marks sync is not yet usable.** Lucas attempted to connect a GitHub connector in his claude.ai account, but as of 2026-07-24 no connector tools are visible/callable from this session (checked via the MCP registry lookup and direct tool search — both came up empty). Cause unconfirmed: could be propagation delay, an incomplete connection, or this session type not exposing claude.ai account connectors the same way the web chat does. **Decision: ship v1 with localStorage-only marks and revisit the GitHub-connector sync as a fast-follow** once connector tools are confirmed observable from a Claude session (required before writing any `window.claude.mcp` call, per the artifact-capabilities rules — no guessing a tool's argument/result shape).
- If the GitHub-connector fast-follow does happen, declaring the `mcp` capability on the Artifact means the page can no longer be shared publicly (a platform-level restriction) — acceptable since Lucas is the only intended viewer.

## Testing / validation plan

- Run the scheduled agent's research logic once manually (not on the cron schedule) before trusting it to run unattended, and sanity-check the output against the required-fields checklist above.
- Verify the Artifact republish actually updates content at the existing (bookmarked) URL rather than minting a new one.
- Verify a mark round-trips end to end: click in the browser → localStorage updates → reload reflects the mark (v1). When the GitHub-connector fast-follow lands, re-verify end to end: click → commit lands in `data/marks.json` on GitHub → reload reflects the mark.
- Verify dedupe: run the research pass twice against the same date range and confirm no paper appears twice in `data/papers.json`.
