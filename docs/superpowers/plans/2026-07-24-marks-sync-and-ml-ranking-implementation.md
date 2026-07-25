# Marks Sync + ML Re-ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Global cross-device marks sync (via a Cloudflare Worker proxy) and a daily-retraining lightweight ML model that re-ranks the 6 flexible daily paper slots based on Lucas's marks.

**Architecture:** A Cloudflare Worker holds the only credential capable of writing `data/marks.json` in the repo; the public site reads marks directly from the public raw file and writes via the Worker. The existing daily GitHub Actions job gains a training/re-ranking step (scikit-learn) that only affects the 6 flexible category slots — the 4 required-category slots are untouched.

**Tech Stack:** Cloudflare Workers (JavaScript, no dependencies), Python + scikit-learn (new dependency, GitHub Actions only) + pytest (existing), vanilla JS (existing site template).

## Global Constraints

- The 4 required-category slots (cell_therapy, regenerative_medicine, clinical_trial, neuroscience) are never re-ranked or affected by the model — only the 6 flexible slots are.
- Only explicit marks are labels: `used` = positive, `not_interested` = negative. Unmarked papers are excluded from training, never treated as positive.
- Cold start: fewer than 15 total labeled examples (across both classes) → skip training entirely, behave exactly as today.
- The public site page must never contain a credential capable of writing to the repo.
- `data/marks.json` lives in the repo (not a separate database) so the daily job can read it with zero extra network calls.

---

## File Structure

```
research-aggregator/
  worker/
    marks-proxy.js        # Cloudflare Worker: the only thing that writes data/marks.json
    wrangler.toml          # Worker deploy config
    README.md               # Deployment steps (for Lucas -- account/secret/deploy)
  data/
    marks.json              # {} initially; {"paper-id": "used"|"not_interested", ...}
  scripts/
    rank_candidates.py      # build_training_set(), train_model(), rank_candidates(), select_flexible_slots()
  tests/
    test_rank_candidates.py
  site/
    artifact_template.html  # modified: marks now fetched/posted, not localStorage
  agent/
    github_actions_prompt.md  # modified: over-generate 12 flexible candidates, run rank_candidates.py
  .github/workflows/
    daily-digest.yml        # modified: pip install scikit-learn before the Claude Code Action step
```

---

### Task 1: Cloudflare Worker (marks write proxy)

**Files:**
- Create: `worker/marks-proxy.js`
- Create: `worker/wrangler.toml`
- Create: `worker/README.md`

**Interfaces:**
- Produces: a deployed HTTP endpoint `POST https://<worker-url>/mark` with body `{"paper_id": string, "mark": "used" | "not_interested" | null}`, consumed by Task 5's site template changes. The exact deployed URL is not known until Task 6 (Lucas deploys it) — Task 5 uses a placeholder that gets filled in during Task 7.

No automated tests for this task (per the design spec: verified manually against the real repo during deployment, not mocked) -- this is pure content creation, verified end-to-end in Task 7.

- [ ] **Step 1: Write worker/marks-proxy.js**

```javascript
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders() });
    }
    if (request.method !== "POST") {
      return jsonResponse({ error: "method not allowed" }, 405);
    }

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

    const owner = "lucasrodriggs-tech";
    const repo = "research-aggregator";
    const path = "data/marks.json";
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${path}`;

    const maxAttempts = 2;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const getResp = await fetch(apiUrl, { headers: githubHeaders(env) });
      if (!getResp.ok) {
        return jsonResponse({ error: `failed to read marks.json: ${getResp.status}` }, 502);
      }
      const getData = await getResp.json();
      const currentContent = JSON.parse(atob(getData.content));
      const sha = getData.sha;

      if (mark === null) {
        delete currentContent[paperId];
      } else {
        currentContent[paperId] = mark;
      }

      const newContentB64 = btoa(JSON.stringify(currentContent, null, 2) + "\n");

      const putResp = await fetch(apiUrl, {
        method: "PUT",
        headers: githubHeaders(env),
        body: JSON.stringify({
          message: `Update mark for ${paperId}`,
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
      return jsonResponse({ error: `failed to write marks.json: ${putResp.status} ${errText}` }, 502);
    }

    return jsonResponse({ error: "exhausted retry attempts" }, 500);
  },
};

function githubHeaders(env) {
  return {
    "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "research-aggregator-marks-worker",
    "Content-Type": "application/json",
  };
}

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

- [ ] **Step 2: Write worker/wrangler.toml**

```toml
name = "research-aggregator-marks"
main = "marks-proxy.js"
compatibility_date = "2026-07-24"
```

- [ ] **Step 3: Write worker/README.md**

```markdown
# Marks proxy Worker

Deploy steps (one-time, must be done by the repo owner -- needs your own
Cloudflare account and a scoped GitHub token):

1. Create a free Cloudflare account at https://dash.cloudflare.com/sign-up if you don't have one.
2. Install Wrangler (Cloudflare's CLI) if not already present:

       npm install -g wrangler

3. From the `worker/` directory, log in (opens a browser):

       wrangler login

4. Create a GitHub Personal Access Token scoped to ONLY this repo, with
   `Contents: Read and write` permission (fine-grained token,
   https://github.com/settings/personal-access-tokens/new -> Repository
   access -> Only select repositories -> research-aggregator -> Permissions
   -> Contents -> Read and write). Copy the token.

5. Set it as a Worker secret (paste the token when prompted -- this stores
   it securely in Cloudflare, never in this repo):

       wrangler secret put GITHUB_TOKEN

6. Deploy:

       wrangler deploy

   This prints the live Worker URL, something like
   `https://research-aggregator-marks.<your-subdomain>.workers.dev`.
   That URL is needed to finish the site integration (see the main repo's
   implementation plan, Task 7).
```

- [ ] **Step 4: Commit**

```bash
git add worker/marks-proxy.js worker/wrangler.toml worker/README.md
git commit -m "Add Cloudflare Worker for global marks write access"
git push
```

---

### Task 2: Data schema + rank_candidates.py (TDD)

**Files:**
- Create: `data/marks.json`
- Create: `scripts/rank_candidates.py`
- Test: `tests/test_rank_candidates.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks (works on plain dicts/lists, same style as `scripts/validate_papers.py` and `scripts/site_data.py`).
- Produces: `build_training_set(papers, marks) -> tuple[list[str], list[int]]`, `train_model(papers, marks) -> dict | None`, `rank_candidates(model, candidates) -> list[dict]`, `select_flexible_slots(model, candidates, slot_count=6) -> list[dict]`, `MIN_LABELED_EXAMPLES: int` -- used by Task 4's updated `agent/github_actions_prompt.md`.

- [ ] **Step 1: Install scikit-learn in the local dev venv**

```bash
.venv\Scripts\python -m pip install scikit-learn
```

- [ ] **Step 2: Create data/marks.json**

```json
{}
```

- [ ] **Step 3: Write the failing tests**

`tests/test_rank_candidates.py`:
```python
from scripts.rank_candidates import (
    build_training_set,
    train_model,
    rank_candidates,
    select_flexible_slots,
    MIN_LABELED_EXAMPLES,
)


def make_paper(id, title, summary="Summary text", category="neuroscience"):
    return {"id": id, "title": title, "summary": summary, "category": category}


def test_build_training_set_only_includes_explicit_marks():
    papers = [make_paper("a", "A"), make_paper("b", "B"), make_paper("c", "C")]
    marks = {"a": "used", "b": "not_interested"}  # c is unmarked, must be excluded
    texts, labels = build_training_set(papers, marks)
    assert len(texts) == 2
    assert labels == [1, 0]


def test_build_training_set_skips_marks_for_unknown_papers():
    papers = [make_paper("a", "A")]
    marks = {"a": "used", "ghost-paper": "not_interested"}
    texts, labels = build_training_set(papers, marks)
    assert len(texts) == 1


def test_train_model_returns_none_below_threshold():
    papers = [make_paper(str(i), f"Title {i}") for i in range(MIN_LABELED_EXAMPLES - 1)]
    marks = {str(i): "used" if i % 2 == 0 else "not_interested" for i in range(MIN_LABELED_EXAMPLES - 1)}
    assert train_model(papers, marks) is None


def test_train_model_returns_none_with_only_one_class():
    papers = [make_paper(str(i), f"Title {i}") for i in range(MIN_LABELED_EXAMPLES)]
    marks = {str(i): "used" for i in range(MIN_LABELED_EXAMPLES)}
    assert train_model(papers, marks) is None


def test_train_model_trains_at_threshold():
    papers = []
    marks = {}
    for i in range(MIN_LABELED_EXAMPLES):
        pid = str(i)
        label = "used" if i % 2 == 0 else "not_interested"
        papers.append(make_paper(pid, f"Title {i}", summary=f"Summary about topic {i % 2}"))
        marks[pid] = label
    model = train_model(papers, marks)
    assert model is not None
    assert "vectorizer" in model and "classifier" in model


def test_rank_candidates_returns_unchanged_order_when_model_is_none():
    candidates = [make_paper("a", "A"), make_paper("b", "B")]
    result = rank_candidates(None, candidates)
    assert result == candidates


def test_select_flexible_slots_returns_requested_count():
    candidates = [make_paper(str(i), f"Title {i}") for i in range(12)]
    result = select_flexible_slots(None, candidates, slot_count=6)
    assert len(result) == 6
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_rank_candidates.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'scripts.rank_candidates'`

- [ ] **Step 5: Implement scripts/rank_candidates.py**

```python
import json

MIN_LABELED_EXAMPLES = 15


def build_training_text(paper):
    return f"{paper['title']} {paper['summary']} {paper['category']}"


def build_training_set(papers, marks):
    texts = []
    labels = []
    papers_by_id = {p["id"]: p for p in papers}
    for paper_id, mark in marks.items():
        if mark not in ("used", "not_interested"):
            continue
        paper = papers_by_id.get(paper_id)
        if paper is None:
            continue
        texts.append(build_training_text(paper))
        labels.append(1 if mark == "used" else 0)
    return texts, labels


def train_model(papers, marks):
    texts, labels = build_training_set(papers, marks)
    if len(texts) < MIN_LABELED_EXAMPLES:
        return None
    if len(set(labels)) < 2:
        return None

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vectorizer = TfidfVectorizer(max_features=500, stop_words="english")
    X = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(max_iter=1000)
    classifier.fit(X, labels)
    return {"vectorizer": vectorizer, "classifier": classifier}


def rank_candidates(model, candidates):
    if model is None:
        return candidates
    texts = [build_training_text(c) for c in candidates]
    X = model["vectorizer"].transform(texts)
    scores = model["classifier"].predict_proba(X)[:, 1]
    scored = list(zip(candidates, scores))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [c for c, _ in scored]


def select_flexible_slots(model, candidates, slot_count=6):
    ranked = rank_candidates(model, candidates)
    return ranked[:slot_count]


if __name__ == "__main__":
    with open("data/papers.json", encoding="utf-8") as f:
        papers = json.load(f)
    with open("data/marks.json", encoding="utf-8") as f:
        marks = json.load(f)
    model = train_model(papers, marks)
    texts, _ = build_training_set(papers, marks)
    if model is None:
        print(f"Cold start: {len(texts)} labeled examples (need {MIN_LABELED_EXAMPLES}), skipping training")
    else:
        print(f"Model trained on {len(texts)} labeled examples")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_rank_candidates.py -v`
Expected: all 6 tests PASS

- [ ] **Step 7: Run the full suite to confirm no regressions**

Run: `.venv\Scripts\python -m pytest tests/ -v`
Expected: all tests (existing 18 + new 6 = 24) PASS

- [ ] **Step 8: Commit**

```bash
git add data/marks.json scripts/rank_candidates.py tests/test_rank_candidates.py
git commit -m "Add marks.json schema and candidate re-ranking logic with tests"
git push
```

---

### Task 3: Install scikit-learn in the GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/daily-digest.yml`

**Interfaces:**
- Consumes: nothing new. Ensures `scripts/rank_candidates.py`'s `import sklearn` (inside `train_model`) succeeds when the daily job's prompt (Task 4) invokes it.

- [ ] **Step 1: Add a Python setup + pip install step before the Claude Code Action step**

In `.github/workflows/daily-digest.yml`, add a new step between "Checkout repository" and "Run daily research digest":

```yaml
      - name: Install Python dependencies
        run: pip install scikit-learn
```

The full file should read:

```yaml
name: Daily Research Digest

on:
  schedule:
    - cron: "4 11 * * *"
  workflow_dispatch: {}

permissions:
  contents: write
  id-token: write

jobs:
  daily-digest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6

      - name: Install Python dependencies
        run: pip install scikit-learn

      - name: Run daily research digest
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          show_full_output: true
          prompt: |
            Follow the instructions in agent/github_actions_prompt.md exactly, in
            order. You are running as a scheduled GitHub Actions workflow with the
            repo already checked out at the current working directory.
          claude_args: |
            --max-turns 150 --dangerously-skip-permissions
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily-digest.yml
git commit -m "Install scikit-learn in CI for the new re-ranking step"
git push
```

---

### Task 4: Update the daily job prompt for over-generation + re-ranking

**Files:**
- Modify: `agent/github_actions_prompt.md`

**Interfaces:**
- Consumes: `scripts/rank_candidates.select_flexible_slots(model, candidates, slot_count=6)`, `scripts/rank_candidates.train_model(papers, marks)` (from Task 2).

- [ ] **Step 1: Replace section 3 ("Research today's 10 papers") with the over-generation version**

Find this text in `agent/github_actions_prompt.md`:

```
## 3. Research today's 10 papers

Categories (must tag every paper with exactly one, from this list):
`cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`,
`ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`.

Rules:
- Exactly 10 new papers today.
- At least 1 each from `cell_therapy`, `regenerative_medicine`,
  `clinical_trial`, `neuroscience`. The remaining 6 may be from any category.
```

Replace with:

```
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
```

- [ ] **Step 2: Insert a new section after the existing section 4 ("Build each paper's JSON entry"), before section 5 ("Self-check before committing")**

Find:

```
Append all 10 new entries to the array in `data/papers.json` (do not remove
or edit any existing entries).

## 5. Self-check before committing
```

Replace with:

```
Append all 10 new entries to the array in `data/papers.json` (do not remove
or edit any existing entries).

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

If it prints \"cold start, using original order\", keep your own first 6
flexible candidates in the order you proposed them and discard the other 6.
If it prints \"model trained\", you'll need to actually run the ranking:
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

## 6. Self-check before committing
```

- [ ] **Step 3: Renumber the remaining sections**

The original sections 5-8 ("Self-check before committing", "Rebuild the site",
"Commit and push", "Done") each shift down by one number since a new
section 5 was inserted. Update the headings:
- `## 5. Self-check before committing` -> `## 6. Self-check before committing` (already done in Step 2's replacement above)
- `## 6. Rebuild the site` -> `## 7. Rebuild the site`
- `## 7. Commit and push` -> `## 8. Commit and push`
- `## 8. Done` -> `## 9. Done`

Also update the commit step to include `data/marks.json` is NOT part of this
commit (the Worker owns writes to that file, not the daily job) -- confirm
the `git add` line still reads exactly `git add data/papers.json docs/index.html`
(no change needed there, just verify it wasn't accidentally widened).

- [ ] **Step 4: Commit**

```bash
git add agent/github_actions_prompt.md
git commit -m "Update daily prompt: over-generate flexible candidates, re-rank via model"
git push
```

---

### Task 5: Update the site to sync marks via fetch instead of localStorage

**Files:**
- Modify: `site/artifact_template.html`

**Interfaces:**
- Produces: the rendered page now reads marks from `MARKS_RAW_URL` on load and writes via `MARK_WRITE_ENDPOINT` (placeholder value, filled in for real in Task 7 once the Worker is deployed).

- [ ] **Step 1: Replace the marks storage constants and load/save functions**

Find (around line 179-197):

```javascript
  var MARKS_KEY = 'research-digest-marks-v1';
  var state = {
    tab: 'today',
    category: null,
    marks: loadMarks(),
    expanded: {}
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
```

Replace with:

```javascript
  var MARK_WRITE_ENDPOINT = 'REPLACE_WITH_WORKER_URL/mark';
  var MARKS_RAW_URL = 'https://raw.githubusercontent.com/lucasrodriggs-tech/research-aggregator/master/data/marks.json';
  var state = {
    tab: 'today',
    category: null,
    marks: {},
    markError: null,
    expanded: {}
  };

  function loadMarks() {
    return fetch(MARKS_RAW_URL, { cache: 'no-store' })
      .then(function (resp) { return resp.ok ? resp.json() : {}; })
      .catch(function () { return {}; });
  }
```

- [ ] **Step 2: Replace setMark to write via the Worker instead of localStorage**

Find (around line 244-252):

```javascript
  function setMark(paperId, value) {
    if (state.marks[paperId] === value) {
      delete state.marks[paperId];
    } else {
      state.marks[paperId] = value;
    }
    saveMarks();
    render();
  }
```

Replace with:

```javascript
  function setMark(paperId, value) {
    var previous = state.marks[paperId];
    var next = previous === value ? null : value;

    if (next === null) {
      delete state.marks[paperId];
    } else {
      state.marks[paperId] = next;
    }
    state.markError = null;
    render();

    fetch(MARK_WRITE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_id: paperId, mark: next })
    }).then(function (resp) {
      if (!resp.ok) throw new Error('save failed');
    }).catch(function () {
      if (previous === undefined) {
        delete state.marks[paperId];
      } else {
        state.marks[paperId] = previous;
      }
      state.markError = paperId;
      render();
    });
  }
```

- [ ] **Step 3: Rename the 'skip' mark value to 'not_interested' (3 occurrences)**

Find (around line 258): `if (mark === 'skip') card.classList.add('marked-skip');`
Replace with: `if (mark === 'not_interested') card.classList.add('marked-skip');`

Find (around line 320): `if (mark === 'skip') skipBtn.classList.add('active-skip');`
Replace with: `if (mark === 'not_interested') skipBtn.classList.add('active-skip');`

Find (around line 323): `setMark(paper.id, 'skip');`
Replace with: `setMark(paper.id, 'not_interested');`

(CSS class names `marked-skip` and `active-skip` are left unchanged -- they're just class names, not the persisted data value, and renaming them isn't necessary.)

- [ ] **Step 4: Add a small error indicator next to the action buttons**

Find (around line 325-327):

```javascript
    actions.appendChild(usedBtn);
    actions.appendChild(skipBtn);
    main.appendChild(actions);
```

Replace with:

```javascript
    actions.appendChild(usedBtn);
    actions.appendChild(skipBtn);
    if (state.markError === paper.id) {
      var errorNote = document.createElement('span');
      errorNote.className = 'mark-error';
      errorNote.textContent = "Couldn't save, try again";
      actions.appendChild(errorNote);
    }
    main.appendChild(actions);
```

Add this CSS rule near the other `.card .actions` rules (find `.card .actions button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }` and add after it):

```css
  .card .actions .mark-error { font-size: 0.75rem; color: var(--critical); align-self: center; }
```

- [ ] **Step 5: Change the bootstrap at the bottom of the script to load marks asynchronously before first render**

Find (at the very end of the script, just before `})();`):

```javascript
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
```

Replace with:

```javascript
  document.getElementById('tab-today').addEventListener('click', function () {
    state.tab = 'today';
    render();
  });
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

- [ ] **Step 6: Rebuild the site locally and manually verify in a browser**

```bash
.venv\Scripts\python -m scripts.build_site
```

Open `docs/index.html` in a browser (or use the Browser pane). Confirm: the page loads without console errors (the fetch to `MARKS_RAW_URL` will succeed since `data/marks.json` is `{}` in the public repo already), clicking "Used for video" updates the UI immediately (optimistic update), and since `MARK_WRITE_ENDPOINT` is still the placeholder value, the write request will fail -- confirm the "Couldn't save, try again" error text appears and the mark reverts. This confirms the optimistic-update-and-rollback path works correctly even before the real Worker URL is wired in.

- [ ] **Step 7: Commit**

```bash
git add site/artifact_template.html
git commit -m "Switch marks from localStorage to fetch-based global sync"
git push
```

---

### Task 6: Deploy the Worker (Lucas only -- cannot be automated)

**Files:** none (infrastructure/account setup only).

- [ ] **Step 1: Lucas follows `worker/README.md`** (written in Task 1) to create a Cloudflare account, install Wrangler, log in, create a scoped GitHub token, set it as a Worker secret, and run `wrangler deploy`.
- [ ] **Step 2: Lucas reports the deployed Worker URL back** (e.g. `https://research-aggregator-marks.someone.workers.dev`) so Task 7 can wire it into the site.

---

### Task 7: Wire in the real Worker URL and validate end to end

**Files:**
- Modify: `site/artifact_template.html`

**Interfaces:**
- Consumes: the real Worker URL from Task 6.

- [ ] **Step 1: Replace the placeholder endpoint**

In `site/artifact_template.html`, find:

```javascript
  var MARK_WRITE_ENDPOINT = 'REPLACE_WITH_WORKER_URL/mark';
```

Replace `REPLACE_WITH_WORKER_URL` with the real Worker URL reported in Task 6 (keep the `/mark` suffix), e.g.:

```javascript
  var MARK_WRITE_ENDPOINT = 'https://research-aggregator-marks.someone.workers.dev/mark';
```

- [ ] **Step 2: Rebuild and republish**

```bash
.venv\Scripts\python -m scripts.build_site
git add site/artifact_template.html docs/index.html
git commit -m "Wire in the real marks-proxy Worker URL"
git push
```

Wait a minute or two for GitHub Pages to redeploy, then open https://lucasrodriggs-tech.github.io/research-aggregator/ in a browser.

- [ ] **Step 3: Verify a mark round-trips for real**

Click "Used for video" on any card. Confirm no error text appears. Then check `data/marks.json` was actually updated:

```bash
git pull
cat data/marks.json
```

Expected: the paper's id now appears with `"used"`. Reload the page in the browser (or open it on a different device/browser) and confirm the mark is still shown -- this is the actual cross-device sync working.

- [ ] **Step 4: Seed test data to verify the cold-start threshold and re-ranking**

The model needs 15+ labeled examples with both classes present before it trains. Manually mark at least 8 real papers "used" and at least 8 "not interested" via the live site (or, if there aren't enough real papers yet, temporarily add synthetic entries to `data/marks.json` for testing, then revert them afterward -- do not leave synthetic test data in the real marks history).

Run the training check locally:

```bash
.venv\Scripts\python -m scripts.rank_candidates
```

Expected: prints `Model trained on N labeled examples` once past the threshold (previously it would have printed the cold-start message).

- [ ] **Step 5: Trigger the daily workflow manually and confirm it completes**

```bash
gh workflow run daily-digest.yml
```

Watch it to completion (same approach as validating the original daily job: poll `gh run view <id> --json status` until it's no longer `in_progress`, then check `conclusion`). Confirm the run succeeds, a new "Research Digest Bot" commit lands with 10 new papers (4 required-category + 6 re-ranked flexible), and the live site updates.
