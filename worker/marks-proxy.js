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
