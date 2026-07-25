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
