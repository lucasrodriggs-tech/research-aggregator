# Research Digest

A daily-refreshed feed of groundbreaking biomedical/neuroscience research papers,
curated for video research. See `docs/superpowers/specs/2026-07-24-research-aggregator-design.md`
for the full design.

## Layout
- `data/papers.json` — full history of every paper ever surfaced (source of truth)
- `scripts/` — validation and site-build logic (Python, tested with pytest)
- `site/artifact_template.html` — the page design; `docs/index.html` is generated, not edited directly
- `agent/github_actions_prompt.md` — the self-contained prompt the daily GitHub Actions workflow runs (current)
- `agent/research_prompt.md`, `agent/routine_prompt.md` — earlier, now-legacy versions of the daily prompt (local scheduled task, Claude Routines) kept for reference; see "History" below
- `.github/workflows/daily-digest.yml` — the actual daily automation, runs on GitHub's own infrastructure

## Rebuilding the site locally

    python -m scripts.build_site

Writes `docs/index.html`, served live by GitHub Pages directly from this repo.

## Running tests

    python -m pytest tests/ -v

## Live site

https://lucasrodriggs-tech.github.io/research-aggregator/

Updates automatically every day via GitHub Actions (`.github/workflows/daily-digest.yml`), authenticated with a Claude Code OAuth token tied to the Pro subscription (no per-run API billing). Runs on GitHub's infrastructure — independent of any local machine.

## History

Two earlier approaches were tried and abandoned before landing on GitHub Actions:
1. **Claude Artifact + local scheduled task** — worked, but only ran while Claude Code Desktop was open on a specific laptop.
2. **Claude Routines (cloud)** — ran independently of any laptop and could read/execute in the repo, but write access back to GitHub was never available (a "Research preview" limitation, not a misconfiguration) — confirmed via direct testing, not assumption.

GitHub Actions solved both problems: it's genuinely serverless, and the workflow's own `contents: write` permission plus `actions/checkout`'s credential setup make `git push` work natively.
